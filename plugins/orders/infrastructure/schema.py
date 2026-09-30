"""Implement Orders' explicit schema initialization.

Create Orders' schema and tables, preserving existing order history on repeated
setup. Inventory's data is not owned here. Serving boot does not run this code.
"""

from sqlalchemy import text

from adapters.persistence_sqlalchemy.session import SessionFactory, transaction


def initialize(factory: SessionFactory) -> None:
    with transaction(factory) as session:
        session.execute(text("CREATE SCHEMA IF NOT EXISTS orders"))
        session.execute(
            text(
                "CREATE TABLE IF NOT EXISTS orders.orders ("
                "  id SERIAL PRIMARY KEY,"
                "  sku VARCHAR NOT NULL,"
                "  qty INT NOT NULL CHECK (qty > 0),"
                "  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP"
                ")"
            )
        )
        session.execute(
            text(
                "ALTER TABLE orders.orders "
                "ADD COLUMN IF NOT EXISTS created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP"
            )
        )
        session.execute(
            text("CREATE INDEX IF NOT EXISTS ix_orders_orders_sku ON orders.orders (sku)")
        )
