"""CLI command contributions for Inventory."""

from collections.abc import Callable, Sequence

from core.runtime_spi.operations import Invoker
from plugins.inventory.public import STOCK_OF, StockOfInput


def make_stock_cli(invoker: Invoker) -> Callable[[Sequence[str]], str]:
    def run(argv: Sequence[str]) -> str:
        if not argv or len(argv) != 1:
            raise ValueError("Usage: stock <sku>")
        sku = argv[0]
        qty = invoker(STOCK_OF, StockOfInput(sku=sku))
        return str(qty)

    return run
