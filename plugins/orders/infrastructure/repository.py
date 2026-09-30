"""SQLAlchemy implementation of OrderRepository."""

from sqlalchemy import text

from adapters.persistence_sqlalchemy.session import SessionFactory, transaction
from plugins.orders.application.ports import OrderRepository
from plugins.orders.public import OrderSummary


class SqlAlchemyOrderRepository(OrderRepository):
    def __init__(self, factory: SessionFactory) -> None:
        self._factory = factory

    def save(self, sku: str, qty: int) -> int:
        with transaction(self._factory) as session:
            stmt = text("INSERT INTO orders.orders (sku, qty) VALUES (:sku, :qty) RETURNING id")
            result = session.execute(stmt, {"sku": sku, "qty": qty})
            row = result.first()
            if row is None:
                raise RuntimeError("Failed to insert order")
            return int(row[0])

    def find_recent(self, sku: str, limit: int) -> tuple[OrderSummary, ...]:
        with transaction(self._factory) as session:
            stmt = text(
                "SELECT id, sku, qty FROM orders.orders "
                "WHERE sku = :sku ORDER BY id DESC LIMIT :limit"
            )
            result = session.execute(stmt, {"sku": sku, "limit": limit})
            rows = result.all()
            return tuple(OrderSummary(order_id=r[0], sku=r[1], qty=r[2]) for r in rows)

    # Aliases for backward compatibility
    def save_order(self, sku: str, qty: int) -> int:
        return self.save(sku, qty)

    def get_recent_orders(self, sku: str, limit: int) -> tuple[OrderSummary, ...]:
        return self.find_recent(sku, limit)
