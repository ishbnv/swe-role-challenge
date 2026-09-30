"""SQLAlchemy persistence adapter for Inventory."""

from sqlalchemy import text

from adapters.persistence_sqlalchemy.session import SessionFactory, transaction
from plugins.inventory.application.ports import StockRepository
from plugins.inventory.domain.stock import deduct_stock
from plugins.inventory.public import InsufficientStock


class SqlAlchemyStockRepository(StockRepository):
    def __init__(self, factory: SessionFactory) -> None:
        self._factory = factory

    def get_stock(self, sku: str) -> int | None:
        with transaction(self._factory) as session:
            result = session.execute(
                text("SELECT qty FROM inventory.stocks WHERE sku = :sku"),
                {"sku": sku},
            ).scalar_one_or_none()
            if result is None:
                return None
            return int(result)

    def reserve_stock(self, sku: str, qty: int) -> None:
        with transaction(self._factory) as session:
            current = session.execute(
                text("SELECT qty FROM inventory.stocks WHERE sku = :sku FOR UPDATE"),
                {"sku": sku},
            ).scalar_one_or_none()
            if current is None:
                raise InsufficientStock(f"SKU '{sku}' not found in inventory")
            current_qty = int(current)
            new_qty = deduct_stock(current_qty, qty)
            session.execute(
                text("UPDATE inventory.stocks SET qty = :new_qty WHERE sku = :sku"),
                {"sku": sku, "new_qty": new_qty},
            )
