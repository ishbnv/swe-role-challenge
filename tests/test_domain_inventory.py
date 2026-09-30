"""Pure unit tests for Inventory domain and application service without database or runtime."""

import unittest

from plugins.inventory.application.service import InventoryService
from plugins.inventory.domain.stock import Stock
from plugins.inventory.public import InsufficientStock


class FakeStockRepository:
    def __init__(self, initial_stock: dict[str, int] | None = None) -> None:
        self.stock = dict(initial_stock) if initial_stock else {}

    def get_stock(self, sku: str) -> int:
        return self.stock.get(sku, 0)

    def reserve_stock(self, sku: str, qty: int) -> None:
        available = self.stock.get(sku, 0)
        if available < qty:
            raise InsufficientStock(f"Insufficient stock for {sku}: {available} < {qty}")
        self.stock[sku] -= qty


class InventoryDomainTests(unittest.TestCase):
    def test_stock_entity_valid(self) -> None:
        stock = Stock(sku="A1", quantity=10)
        stock.reserve(3)
        self.assertEqual(stock.quantity, 7)

    def test_stock_entity_negative_initial_quantity_fails(self) -> None:
        with self.assertRaises(ValueError):
            Stock(sku="A1", quantity=-1)

    def test_stock_entity_reserve_nonpositive_fails(self) -> None:
        stock = Stock(sku="A1", quantity=10)
        with self.assertRaises(ValueError):
            stock.reserve(0)
        with self.assertRaises(ValueError):
            stock.reserve(-5)

    def test_stock_entity_insufficient_stock_fails(self) -> None:
        stock = Stock(sku="A1", quantity=5)
        with self.assertRaises(InsufficientStock):
            stock.reserve(6)
        self.assertEqual(stock.quantity, 5)  # unchanged


class InventoryServiceTests(unittest.TestCase):
    def test_service_successful_reserve(self) -> None:
        repo = FakeStockRepository({"A1": 10})
        service = InventoryService(repo)

        service.reserve_stock("A1", 4)
        self.assertEqual(service.get_stock("A1"), 6)

    def test_service_rejects_nonpositive_quantity(self) -> None:
        repo = FakeStockRepository({"A1": 10})
        service = InventoryService(repo)

        with self.assertRaises(ValueError):
            service.reserve_stock("A1", 0)
        with self.assertRaises(ValueError):
            service.reserve_stock("A1", -3)
        self.assertEqual(service.get_stock("A1"), 10)

    def test_service_rejects_insufficient_stock(self) -> None:
        repo = FakeStockRepository({"A1": 3})
        service = InventoryService(repo)

        with self.assertRaises(InsufficientStock):
            service.reserve_stock("A1", 5)
        self.assertEqual(service.get_stock("A1"), 3)

    def test_service_unknown_sku_returns_zero(self) -> None:
        repo = FakeStockRepository()
        service = InventoryService(repo)
        self.assertEqual(service.get_stock("UNKNOWN"), 0)


if __name__ == "__main__":
    unittest.main()
