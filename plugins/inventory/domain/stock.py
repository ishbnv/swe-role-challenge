"""Domain logic for Inventory."""

from dataclasses import dataclass

from plugins.inventory.public import InsufficientStock


def validate_qty(qty: int) -> None:
    if qty <= 0:
        raise ValueError(f"Quantity must be positive, got {qty}")


def deduct_stock(current_stock: int, qty: int) -> int:
    validate_qty(qty)
    if current_stock < qty:
        raise InsufficientStock(f"Insufficient stock: requested {qty}, available {current_stock}")
    return current_stock - qty


@dataclass
class Stock:
    sku: str
    current: int

    def __init__(
        self,
        sku: str,
        current: int | None = None,
        qty: int | None = None,
        quantity: int | None = None,
    ) -> None:
        val = current if current is not None else (qty if qty is not None else quantity)
        if val is None:
            raise TypeError("current, qty, or quantity is required")
        if val < 0:
            raise ValueError(f"Stock quantity cannot be negative for SKU '{sku}', got {val}")
        self.sku = sku
        self.current = val

    @property
    def qty(self) -> int:
        return self.current

    @qty.setter
    def qty(self, value: int) -> None:
        if value < 0:
            raise ValueError(f"Stock quantity cannot be negative for SKU '{self.sku}', got {value}")
        self.current = value

    @property
    def quantity(self) -> int:
        return self.current

    @quantity.setter
    def quantity(self, value: int) -> None:
        self.qty = value

    def reserve(self, qty: int) -> None:
        self.current = deduct_stock(self.current, qty)

    def decrease(self, qty: int) -> None:
        self.reserve(qty)
