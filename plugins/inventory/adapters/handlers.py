"""Operation handlers for Inventory."""

from collections.abc import Callable

from plugins.inventory.application.use_cases import GetStockUseCase, ReserveStockUseCase
from plugins.inventory.public import ReserveStockInput, StockOfInput


def make_stock_of_handler(use_case: GetStockUseCase) -> Callable[[StockOfInput], int]:
    def handle_stock_of(inp: StockOfInput) -> int:
        return use_case.execute(inp.sku)

    return handle_stock_of


def make_reserve_stock_handler(
    use_case: ReserveStockUseCase,
) -> Callable[[ReserveStockInput], None]:
    def handle_reserve_stock(inp: ReserveStockInput) -> None:
        use_case.execute(inp.sku, inp.qty)

    return handle_reserve_stock
