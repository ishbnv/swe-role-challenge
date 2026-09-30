"""Application ports for Orders."""

from typing import Protocol

from plugins.orders.public import OrderSummary


class OrderRepository(Protocol):
    def save(self, sku: str, qty: int) -> int: ...
    def find_recent(self, sku: str, limit: int) -> tuple[OrderSummary, ...]: ...


class StockReservationPort(Protocol):
    def reserve(self, sku: str, qty: int) -> None: ...
