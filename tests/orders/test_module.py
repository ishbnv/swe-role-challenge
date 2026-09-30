"""Tests for orders_module declaration and assembly with a mock BootContext."""

import unittest
from collections.abc import Callable
from typing import Any
from unittest.mock import MagicMock

from adapters.persistence_sqlalchemy.bootstrap import SESSION_FACTORY
from core.runtime_spi import INVOKER, ArtifactKey, BootContext, Command, Invoker, Operation
from plugins.inventory.public import RESERVE_STOCK, ReserveStockInput
from plugins.orders.bootstrap.module import orders_module
from plugins.orders.public import (
    PLACE_ORDER,
    RECENT_ORDERS,
    OrderSummary,
    PlaceOrderInput,
    RecentOrdersInput,
)


class MockBootContext(BootContext):
    def __init__(self, artifacts: dict[ArtifactKey[Any], Any]) -> None:
        self._artifacts = artifacts
        self.required_keys: list[ArtifactKey[Any]] = []
        self.provided_artifacts: dict[ArtifactKey[Any], Any] = {}
        self.bound_handlers: dict[Operation[Any, Any], Callable[[Any], Any]] = {}
        self.contributed_commands: dict[str, Command] = {}

    def require[T](self, key: ArtifactKey[T]) -> T:
        self.required_keys.append(key)
        if key not in self._artifacts:
            raise KeyError(f"Missing artifact: {key}")
        return self._artifacts[key]  # pyright: ignore[reportReturnType]

    def provide[T](self, key: ArtifactKey[T], value: T) -> None:
        self.provided_artifacts[key] = value

    def bind[I, O](self, operation: Operation[I, O], handler: Callable[[I], O]) -> None:
        self.bound_handlers[operation] = handler  # pyright: ignore[reportArgumentType]

    def contribute(self, command: Command) -> None:
        self.contributed_commands[command.name] = command


class OrdersModuleTests(unittest.TestCase):
    def test_module_declarations(self) -> None:
        self.assertEqual(orders_module.name, "orders")
        self.assertEqual(orders_module.operations, frozenset({PLACE_ORDER, RECENT_ORDERS}))
        self.assertEqual(orders_module.uses, frozenset({RESERVE_STOCK}))
        self.assertEqual(len(orders_module.steps), 1)

        step = orders_module.steps[0]
        self.assertEqual(step.name, "orders.assemble")
        self.assertEqual(step.requires, frozenset({SESSION_FACTORY, INVOKER}))
        self.assertEqual(step.provides, frozenset())

    def test_assembly_registers_handlers_and_commands(self) -> None:
        mock_factory = MagicMock()
        mock_invoker = MagicMock(spec=Invoker)

        ctx = MockBootContext(
            {
                SESSION_FACTORY: mock_factory,
                INVOKER: mock_invoker,
            }
        )

        # Run step
        orders_module.steps[0].run(ctx)

        # 1. Check requires
        self.assertIn(SESSION_FACTORY, ctx.required_keys)
        self.assertIn(INVOKER, ctx.required_keys)

        # 2. Check bound handlers
        self.assertIn(PLACE_ORDER, ctx.bound_handlers)
        self.assertIn(RECENT_ORDERS, ctx.bound_handlers)

        # 3. Check contributed commands
        self.assertIn("place", ctx.contributed_commands)
        self.assertIn("recent", ctx.contributed_commands)

    def test_place_command_execution(self) -> None:
        mock_factory = MagicMock()
        mock_invoker = MagicMock(spec=Invoker)
        ctx = MockBootContext(
            {
                SESSION_FACTORY: mock_factory,
                INVOKER: mock_invoker,
            }
        )
        orders_module.steps[0].run(ctx)

        place_cmd = ctx.contributed_commands["place"]

        # Success case
        res = place_cmd.run(["A1", "3"])
        self.assertEqual(res, "placed")
        mock_invoker.assert_called_once_with(PLACE_ORDER, PlaceOrderInput(sku="A1", qty=3))

        # Invalid arguments count
        with self.assertRaises(ValueError) as err:
            place_cmd.run(["A1"])
        self.assertIn("Usage: place <sku> <qty>", str(err.exception))

        # Invalid quantity format
        with self.assertRaises(ValueError) as err:
            place_cmd.run(["A1", "not_a_number"])
        self.assertIn("Invalid quantity", str(err.exception))

    def test_recent_command_execution(self) -> None:
        mock_factory = MagicMock()
        mock_invoker = MagicMock(spec=Invoker)
        ctx = MockBootContext(
            {
                SESSION_FACTORY: mock_factory,
                INVOKER: mock_invoker,
            }
        )
        orders_module.steps[0].run(ctx)

        recent_cmd = ctx.contributed_commands["recent"]

        # Formatted output
        mock_invoker.return_value = (
            OrderSummary(order_id=2, sku="A1", qty=5),
            OrderSummary(order_id=1, sku="A1", qty=2),
        )
        res = recent_cmd.run(["A1", "2"])
        self.assertEqual(res, "5,2")
        mock_invoker.assert_called_with(RECENT_ORDERS, RecentOrdersInput(sku="A1", limit=2))

        # Empty output when no orders found
        mock_invoker.return_value = ()
        res_empty = recent_cmd.run(["A1", "5"])
        self.assertEqual(res_empty, "")

        # Invalid arguments count
        with self.assertRaises(ValueError) as err:
            recent_cmd.run(["A1"])
        self.assertIn("Usage: recent <sku> <limit>", str(err.exception))

        # Invalid limit format
        with self.assertRaises(ValueError) as err:
            recent_cmd.run(["A1", "abc"])
        self.assertIn("Invalid limit", str(err.exception))

    def test_bound_handlers_execution(self) -> None:
        # Mock session and factory for repository
        mock_session = MagicMock()
        # Mock execute returning scalar order id
        mock_first_result = MagicMock()
        mock_first_result.first.return_value = (42,)
        mock_session.execute.return_value = mock_first_result

        mock_context_manager = MagicMock()
        mock_context_manager.__enter__.return_value = mock_session
        mock_factory = MagicMock()
        mock_factory.begin.return_value = mock_context_manager

        mock_invoker = MagicMock(spec=Invoker)

        ctx = MockBootContext(
            {
                SESSION_FACTORY: mock_factory,
                INVOKER: mock_invoker,
            }
        )
        orders_module.steps[0].run(ctx)

        # PLACE_ORDER handler
        place_handler = ctx.bound_handlers[PLACE_ORDER]
        place_handler(PlaceOrderInput(sku="A1", qty=4))

        # Verifies reservation was called via invoker
        mock_invoker.assert_called_once_with(RESERVE_STOCK, ReserveStockInput(sku="A1", qty=4))

        # RECENT_ORDERS handler
        mock_rows = MagicMock()
        mock_rows.all.return_value = [(10, "A1", 4)]
        mock_session.execute.return_value = mock_rows

        recent_handler = ctx.bound_handlers[RECENT_ORDERS]
        results = recent_handler(RecentOrdersInput(sku="A1", limit=1))
        self.assertEqual(results, (OrderSummary(order_id=10, sku="A1", qty=4),))


if __name__ == "__main__":
    unittest.main()
