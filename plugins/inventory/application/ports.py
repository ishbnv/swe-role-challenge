"""Application ports for Inventory."""

from typing import Protocol


class StockRepository(Protocol):
    def get_stock(self, sku: str) -> int | None: ...

    def reserve_stock(self, sku: str, qty: int) -> None: ...
