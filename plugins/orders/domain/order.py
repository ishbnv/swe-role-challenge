"""Domain models and business validation rules for Orders."""

from dataclasses import dataclass
from datetime import datetime


def validate_qty(qty: int) -> None:
    if qty <= 0:
        raise ValueError(f"Order quantity must be positive, got {qty}")


def validate_limit(limit: int) -> None:
    if limit <= 0:
        raise ValueError(f"Limit must be positive, got {limit}")


@dataclass(frozen=True)
class Order:
    sku: str
    qty: int
    order_id: int | None = None
    created_at: datetime | None = None

    def __post_init__(self) -> None:
        validate_qty(self.qty)
