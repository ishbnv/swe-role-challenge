"""SQLAlchemy models for Inventory schema."""

from sqlalchemy import CheckConstraint, Integer, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class InventoryBase(DeclarativeBase):
    pass


class StockModel(InventoryBase):
    __tablename__ = "stocks"
    __table_args__ = (
        CheckConstraint("qty >= 0", name="check_qty_non_negative"),
        {"schema": "inventory"},
    )

    sku: Mapped[str] = mapped_column(String, primary_key=True)
    qty: Mapped[int] = mapped_column(Integer, nullable=False)
