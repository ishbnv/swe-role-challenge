"""Unit tests for Orders domain entity, validation rules, and use cases."""

import unittest

from plugins.inventory.public import InsufficientStock
from plugins.orders.application.ports import OrderRepository, StockReservationPort
from plugins.orders.application.use_cases import GetRecentOrdersUseCase, PlaceOrderUseCase
from plugins.orders.domain.order import Order, validate_limit, validate_qty
from plugins.orders.public import OrderSummary


class FakeOrderRepository(OrderRepository):
    def __init__(self) -> None:
        self.orders: list[tuple[int, str, int]] = []
        self._next_id = 1

    def save(self, sku: str, qty: int) -> int:
        order_id = self._next_id
        self._next_id += 1
        self.orders.append((order_id, sku, qty))
        return order_id

    def find_recent(self, sku: str, limit: int) -> tuple[OrderSummary, ...]:
        matched = [o for o in self.orders if o[1] == sku]
        # Sort descending by order_id
        matched.sort(key=lambda o: o[0], reverse=True)
        limited = matched[:limit]
        return tuple(OrderSummary(order_id=o[0], sku=o[1], qty=o[2]) for o in limited)


class FakeStockReservationPort(StockReservationPort):
    def __init__(self, should_fail: bool = False) -> None:
        self.should_fail = should_fail
        self.reserve_calls: list[tuple[str, int]] = []

    def reserve(self, sku: str, qty: int) -> None:
        self.reserve_calls.append((sku, qty))
        if self.should_fail:
            raise InsufficientStock(f"Insufficient stock for {sku}")


class OrderDomainTests(unittest.TestCase):
    def test_order_creation_with_valid_quantity(self) -> None:
        order = Order(sku="A1", qty=5)
        self.assertEqual(order.sku, "A1")
        self.assertEqual(order.qty, 5)
        self.assertIsNone(order.order_id)

    def test_order_creation_rejects_nonpositive_quantity(self) -> None:
        with self.assertRaises(ValueError) as ctx_zero:
            Order(sku="A1", qty=0)
        self.assertIn("positive", str(ctx_zero.exception))

        with self.assertRaises(ValueError) as ctx_neg:
            Order(sku="A1", qty=-3)
        self.assertIn("positive", str(ctx_neg.exception))

    def test_validate_qty_rules(self) -> None:
        validate_qty(1)
        validate_qty(100)
        with self.assertRaises(ValueError):
            validate_qty(0)
        with self.assertRaises(ValueError):
            validate_qty(-5)

    def test_validate_limit_rules(self) -> None:
        validate_limit(1)
        validate_limit(10)
        with self.assertRaises(ValueError):
            validate_limit(0)
        with self.assertRaises(ValueError):
            validate_limit(-1)


class PlaceOrderUseCaseTests(unittest.TestCase):
    def test_place_order_success(self) -> None:
        repo = FakeOrderRepository()
        port = FakeStockReservationPort(should_fail=False)
        use_case = PlaceOrderUseCase(order_repo=repo, stock_reservation=port)

        order_id = use_case.execute("A1", 3)

        self.assertEqual(order_id, 1)
        self.assertEqual(port.reserve_calls, [("A1", 3)])
        self.assertEqual(len(repo.orders), 1)
        self.assertEqual(repo.orders[0], (1, "A1", 3))

    def test_place_order_insufficient_stock_does_not_create_order(self) -> None:
        repo = FakeOrderRepository()
        port = FakeStockReservationPort(should_fail=True)
        use_case = PlaceOrderUseCase(order_repo=repo, stock_reservation=port)

        with self.assertRaises(InsufficientStock):
            use_case.execute("A1", 10)

        # Reservation was attempted
        self.assertEqual(port.reserve_calls, [("A1", 10)])
        # Order was NOT created in repository
        self.assertEqual(len(repo.orders), 0)

    def test_place_order_rejects_nonpositive_quantity_before_reservation(self) -> None:
        repo = FakeOrderRepository()
        port = FakeStockReservationPort(should_fail=False)
        use_case = PlaceOrderUseCase(order_repo=repo, stock_reservation=port)

        for invalid_qty in (0, -1, -10):
            with self.subTest(qty=invalid_qty):
                with self.assertRaises(ValueError):
                    use_case.execute("A1", invalid_qty)

        # Stock reservation was NEVER called
        self.assertEqual(len(port.reserve_calls), 0)
        # Order was NEVER saved
        self.assertEqual(len(repo.orders), 0)


class GetRecentOrdersUseCaseTests(unittest.TestCase):
    def test_get_recent_orders_limit_validation(self) -> None:
        repo = FakeOrderRepository()
        use_case = GetRecentOrdersUseCase(order_repo=repo)

        for invalid_limit in (0, -1, -5):
            with self.subTest(limit=invalid_limit):
                with self.assertRaises(ValueError):
                    use_case.execute("A1", invalid_limit)

    def test_get_recent_orders_returns_ordered_limited_summaries(self) -> None:
        repo = FakeOrderRepository()
        repo.save("A1", 2)
        repo.save("A1", 5)
        repo.save("A1", 7)
        repo.save("B2", 9)

        use_case = GetRecentOrdersUseCase(order_repo=repo)
        results = use_case.execute("A1", 2)

        self.assertEqual(len(results), 2)
        self.assertEqual(results[0].qty, 7)
        self.assertEqual(results[1].qty, 5)

    def test_get_recent_orders_unknown_sku_returns_empty_tuple(self) -> None:
        repo = FakeOrderRepository()
        repo.save("A1", 5)

        use_case = GetRecentOrdersUseCase(order_repo=repo)
        results = use_case.execute("UNKNOWN_SKU", 5)

        self.assertEqual(results, ())


if __name__ == "__main__":
    unittest.main()
