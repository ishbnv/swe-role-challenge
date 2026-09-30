"""Integration tests exercising the runtime, CLI, and plugins against PostgreSQL."""

import unittest

import pytest
from sqlalchemy import text

from adapters.persistence_sqlalchemy.bootstrap import persistence_module
from adapters.persistence_sqlalchemy.session import open_database
from apps.composition import build_cli, open_cli
from apps.settings import database_url
from core.kernel.kernel import Kernel
from plugins.inventory.infrastructure.schema import initialize as initialize_inventory
from plugins.inventory.module import inventory_module
from plugins.inventory.public import STOCK_OF, InsufficientStock, StockOfInput
from plugins.orders.infrastructure.schema import initialize as initialize_orders


@pytest.mark.postgres
class PostgresIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        # Reset tables for isolated integration testing
        url = database_url()
        with open_database(url) as resources:
            with resources.engine.begin() as conn:
                conn.execute(text("DROP SCHEMA IF EXISTS inventory CASCADE"))
                conn.execute(text("DROP SCHEMA IF EXISTS orders CASCADE"))
            initialize_inventory(resources.session_factory)
            initialize_orders(resources.session_factory)

    def test_stock_command_reads_initial_committed_stock(self) -> None:
        with open_cli() as cli:
            self.assertEqual(cli.run(["stock", "A1"]), "10")

    def test_stock_command_unknown_sku_returns_zero(self) -> None:
        with open_cli() as cli:
            self.assertEqual(cli.run(["stock", "UNKNOWN"]), "0")

    def test_place_order_and_recent_orders_flow(self) -> None:
        with open_cli() as cli:
            # 1. Verify initial stock
            self.assertEqual(cli.run(["stock", "A1"]), "10")

            # 2. Place order for 3
            result = cli.run(["place", "A1", "3"])
            self.assertEqual(result, "placed")

            # 3. Stock reduced to 7
            self.assertEqual(cli.run(["stock", "A1"]), "7")

            # 4. Recent orders returns "3"
            self.assertEqual(cli.run(["recent", "A1", "5"]), "3")

            # 5. Place second order for 2
            self.assertEqual(cli.run(["place", "A1", "2"]), "placed")

            # 6. Stock reduced to 5
            self.assertEqual(cli.run(["stock", "A1"]), "5")

            # 7. Recent returns newest first "2,3"
            self.assertEqual(cli.run(["recent", "A1", "2"]), "2,3")

    def test_rejected_order_leaves_stock_and_orders_unchanged(self) -> None:
        with open_cli() as cli:
            # Initial order
            cli.run(["place", "A1", "4"])
            self.assertEqual(cli.run(["stock", "A1"]), "6")

            # Try to place order exceeding available stock (6)
            with self.assertRaises(InsufficientStock):
                cli.run(["place", "A1", "10"])

            # Stock is still 6
            self.assertEqual(cli.run(["stock", "A1"]), "6")
            # Orders table still has only the first order
            self.assertEqual(cli.run(["recent", "A1", "5"]), "4")

    def test_place_nonpositive_quantity_fails_without_modifications(self) -> None:
        with open_cli() as cli:
            with self.assertRaises(ValueError):
                cli.run(["place", "A1", "0"])
            with self.assertRaises(ValueError):
                cli.run(["place", "A1", "-3"])

            self.assertEqual(cli.run(["stock", "A1"]), "10")
            self.assertEqual(cli.run(["recent", "A1", "5"]), "")

    def test_recent_orders_unknown_sku_returns_empty_string(self) -> None:
        with open_cli() as cli:
            self.assertEqual(cli.run(["recent", "NONEXISTENT", "5"]), "")

    def test_repeated_schema_initialization_preserves_stock_and_orders(self) -> None:
        with open_cli() as cli:
            cli.run(["place", "A1", "3"])
            self.assertEqual(cli.run(["stock", "A1"]), "7")
            self.assertEqual(cli.run(["recent", "A1", "5"]), "3")

        # Run initialize again
        url = database_url()
        with open_database(url) as resources:
            initialize_inventory(resources.session_factory)
            initialize_orders(resources.session_factory)

        # Verify data was preserved
        with open_cli() as cli:
            self.assertEqual(cli.run(["stock", "A1"]), "7")
            self.assertEqual(cli.run(["recent", "A1", "5"]), "3")

    def test_inventory_works_without_orders_installed(self) -> None:
        """Inventory must work without Orders installed."""
        url = database_url()
        with open_database(url) as resources:
            cli = build_cli((inventory_module, persistence_module(resources)))
            self.assertEqual(cli.run(["stock", "A1"]), "10")

            # Can also invoke public operations directly on the App
            app = Kernel().boot((inventory_module, persistence_module(resources)))
            stock = app.invoke(STOCK_OF, StockOfInput(sku="A1"))
            self.assertEqual(stock, 10)


if __name__ == "__main__":
    unittest.main()
