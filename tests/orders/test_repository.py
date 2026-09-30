"""Integration tests for SqlAlchemyOrderRepository against PostgreSQL."""

import unittest

import pytest
from sqlalchemy import text

from adapters.persistence_sqlalchemy.session import open_database
from apps.settings import database_url
from plugins.orders.infrastructure.repository import SqlAlchemyOrderRepository
from plugins.orders.infrastructure.schema import initialize as initialize_orders


@pytest.mark.postgres
class SqlAlchemyOrderRepositoryIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        url = database_url()
        with open_database(url) as resources:
            self.factory = resources.session_factory
            with resources.engine.begin() as conn:
                conn.execute(text("DROP SCHEMA IF EXISTS orders CASCADE"))
            initialize_orders(self.factory)
            self.repo = SqlAlchemyOrderRepository(self.factory)

    def test_save_returns_sequential_order_ids(self) -> None:
        id1 = self.repo.save("A1", 3)
        id2 = self.repo.save("A1", 5)
        id3 = self.repo.save("B2", 1)

        self.assertIsInstance(id1, int)
        self.assertIsInstance(id2, int)
        self.assertIsInstance(id3, int)
        self.assertGreater(id2, id1)
        self.assertGreater(id3, id2)

    def test_find_recent_filters_by_sku_and_sorts_descending(self) -> None:
        self.repo.save("A1", 2)
        self.repo.save("B2", 100)
        self.repo.save("A1", 4)
        self.repo.save("A1", 6)

        results = self.repo.find_recent("A1", 10)

        # Only A1 orders returned
        self.assertEqual(len(results), 3)
        self.assertTrue(all(r.sku == "A1" for r in results))

        # Sorted by id DESC (newest first): 6, 4, 2
        self.assertEqual([r.qty for r in results], [6, 4, 2])
        self.assertGreater(results[0].order_id, results[1].order_id)
        self.assertGreater(results[1].order_id, results[2].order_id)

    def test_find_recent_applies_limit_in_sql(self) -> None:
        for qty in range(1, 6):
            self.repo.save("A1", qty)

        # Fetch limit 2
        results = self.repo.find_recent("A1", 2)
        self.assertEqual(len(results), 2)
        # Should be the two newest orders: 5 and 4
        self.assertEqual([r.qty for r in results], [5, 4])

        # Fetch limit 1
        results_1 = self.repo.find_recent("A1", 1)
        self.assertEqual(len(results_1), 1)
        self.assertEqual(results_1[0].qty, 5)

    def test_find_recent_unknown_sku_returns_empty_tuple(self) -> None:
        self.repo.save("A1", 5)
        results = self.repo.find_recent("NONEXISTENT", 5)
        self.assertEqual(results, ())

    def test_repeated_schema_initialization_preserves_orders(self) -> None:
        self.repo.save("A1", 7)
        self.assertEqual(len(self.repo.find_recent("A1", 10)), 1)

        # Run initialize again
        initialize_orders(self.factory)

        # Order must still be present
        orders = self.repo.find_recent("A1", 10)
        self.assertEqual(len(orders), 1)
        self.assertEqual(orders[0].qty, 7)


if __name__ == "__main__":
    unittest.main()
