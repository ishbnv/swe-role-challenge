"""Frozen public Inventory behavior; no host or implementation dependency."""

from typing import NamedTuple

from core.runtime_spi import Operation


class ReserveStockInput(NamedTuple):
    sku: str
    qty: int


class StockOfInput(NamedTuple):
    sku: str


class InsufficientStock(Exception):
    """Reservation was rejected without changing stock."""


RESERVE_STOCK = Operation("inventory.reserve_stock", ReserveStockInput, type(None))
STOCK_OF = Operation("inventory.stock_of", StockOfInput, int)
