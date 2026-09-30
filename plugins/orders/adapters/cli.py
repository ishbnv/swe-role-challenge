"""CLI command contributions for Orders."""

from collections.abc import Sequence

from core.runtime_spi import Command, Invoker
from plugins.orders.public import (
    PLACE_ORDER,
    RECENT_ORDERS,
    PlaceOrderInput,
    RecentOrdersInput,
)


def create_place_command(invoker: Invoker) -> Command:
    def run_place(argv: Sequence[str]) -> str:
        if len(argv) != 2:
            raise ValueError("Usage: place <sku> <qty>")
        sku = argv[0]
        try:
            qty = int(argv[1])
        except ValueError as e:
            raise ValueError(f"Invalid quantity: '{argv[1]}'") from e
        invoker(PLACE_ORDER, PlaceOrderInput(sku=sku, qty=qty))
        return "placed"

    return Command("place", run_place)


def create_recent_command(invoker: Invoker) -> Command:
    def run_recent(argv: Sequence[str]) -> str:
        if len(argv) != 2:
            raise ValueError("Usage: recent <sku> <limit>")
        sku = argv[0]
        try:
            limit = int(argv[1])
        except ValueError as e:
            raise ValueError(f"Invalid limit: '{argv[1]}'") from e
        summaries = invoker(RECENT_ORDERS, RecentOrdersInput(sku=sku, limit=limit))
        if not summaries:
            return ""
        return ",".join(str(s.qty) for s in summaries)

    return Command("recent", run_recent)
