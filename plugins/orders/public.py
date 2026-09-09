"""Frozen public Orders behavior; implementations and storage stay private."""

from typing import NamedTuple

from core.runtime_spi import Operation


class PlaceOrderInput(NamedTuple):
    sku: str
    qty: int


PLACE_ORDER = Operation("orders.place_order", PlaceOrderInput, type(None))


class RecentOrdersInput(NamedTuple):
    sku: str
    limit: int


class OrderSummary(NamedTuple):
    order_id: int
    sku: str
    qty: int


RECENT_ORDERS: Operation[RecentOrdersInput, tuple[OrderSummary, ...]] = Operation(
    "orders.recent", RecentOrdersInput, tuple
)
