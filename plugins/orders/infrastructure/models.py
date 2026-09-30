"""SQLAlchemy models for Orders schema."""

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Integer, String, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class OrdersBase(DeclarativeBase):
    pass


class OrderModel(OrdersBase):
    __tablename__ = "orders"
    __table_args__ = (
        CheckConstraint("qty > 0", name="check_order_qty_positive"),
        {"schema": "orders"},
    )

    order_id: Mapped[int] = mapped_column("id", Integer, primary_key=True, autoincrement=True)
    sku: Mapped[str] = mapped_column(String, nullable=False, index=True)
    qty: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
