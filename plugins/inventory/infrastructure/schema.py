"""Implement Inventory's explicit schema initialization.

Create Inventory's schema and tables. Initialize A1 = 10 only when absent;
repeated setup must preserve existing stock. Serving boot does not run this code.
"""

from sqlalchemy import text

from adapters.persistence_sqlalchemy.session import SessionFactory, transaction


def initialize(factory: SessionFactory) -> None:
    with transaction(factory) as session:
        session.execute(text("CREATE SCHEMA IF NOT EXISTS inventory"))
        session.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS inventory.stocks (
                    sku VARCHAR PRIMARY KEY,
                    qty INTEGER NOT NULL CHECK (qty >= 0)
                )
                """
            )
        )
        session.execute(
            text(
                """
                INSERT INTO inventory.stocks (sku, qty)
                VALUES ('A1', 10)
                ON CONFLICT (sku) DO NOTHING
                """
            )
        )
