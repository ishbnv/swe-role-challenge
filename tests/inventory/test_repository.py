"""Integration tests for Inventory repository and schema against PostgreSQL."""

import pytest
from sqlalchemy import text

from adapters.persistence_sqlalchemy.session import open_database
from apps.settings import database_url
from plugins.inventory.infrastructure.repository import SqlAlchemyStockRepository
from plugins.inventory.infrastructure.schema import initialize
from plugins.inventory.public import InsufficientStock


@pytest.mark.postgres
def test_inventory_schema_init_and_seed_preservation() -> None:
    with open_database(database_url()) as resources:
        factory = resources.session_factory

        # Reset schema for a clean test run
        with resources.engine.begin() as conn:
            conn.execute(text("DROP SCHEMA IF EXISTS inventory CASCADE"))

        # Initialize schema and seed A1 = 10
        initialize(factory)
        repo = SqlAlchemyStockRepository(factory)

        # Make sure A1 exists with 10
        stock = repo.get_stock("A1")
        assert stock == 10

        # Reserve some stock
        repo.reserve_stock("A1", 3)
        assert repo.get_stock("A1") == 7

        # Repeated initialize must NOT reset stock to 10 (ON CONFLICT DO NOTHING)
        initialize(factory)
        assert repo.get_stock("A1") == 7


@pytest.mark.postgres
def test_inventory_repository_get_stock_unknown_sku() -> None:
    with open_database(database_url()) as resources:
        factory = resources.session_factory
        initialize(factory)
        repo = SqlAlchemyStockRepository(factory)

        assert repo.get_stock("UNKNOWN_SKU_123") is None


@pytest.mark.postgres
def test_inventory_reserve_insufficient_stock() -> None:
    with open_database(database_url()) as resources:
        factory = resources.session_factory
        # Reset schema
        with resources.engine.begin() as conn:
            conn.execute(text("DROP SCHEMA IF EXISTS inventory CASCADE"))
        initialize(factory)
        repo = SqlAlchemyStockRepository(factory)

        # Try to reserve more than available (available is 10)
        with pytest.raises(InsufficientStock):
            repo.reserve_stock("A1", 11)

        # Stock remains untouched
        assert repo.get_stock("A1") == 10


@pytest.mark.postgres
def test_inventory_reserve_nonexistent_sku() -> None:
    with open_database(database_url()) as resources:
        factory = resources.session_factory
        initialize(factory)
        repo = SqlAlchemyStockRepository(factory)

        with pytest.raises(InsufficientStock):
            repo.reserve_stock("NONEXISTENT_SKU", 1)


@pytest.mark.postgres
def test_inventory_reserve_negative_or_zero_qty() -> None:
    with open_database(database_url()) as resources:
        factory = resources.session_factory
        initialize(factory)
        repo = SqlAlchemyStockRepository(factory)

        with pytest.raises(ValueError, match="positive"):
            repo.reserve_stock("A1", 0)

        with pytest.raises(ValueError, match="positive"):
            repo.reserve_stock("A1", -5)

        # Stock remains unchanged
        assert repo.get_stock("A1") == 10
