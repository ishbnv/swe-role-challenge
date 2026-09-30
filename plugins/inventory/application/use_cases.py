"""Use cases for Inventory."""

from plugins.inventory.application.ports import StockRepository
from plugins.inventory.domain.stock import validate_qty


class GetStockUseCase:
    def __init__(self, repo: StockRepository) -> None:
        self._repo = repo

    def execute(self, sku: str) -> int:
        stock = self._repo.get_stock(sku)
        return stock if stock is not None else 0

    def __call__(self, sku: str) -> int:
        return self.execute(sku)


class ReserveStockUseCase:
    def __init__(self, repo: StockRepository) -> None:
        self._repo = repo

    def execute(self, sku: str, qty: int) -> None:
        validate_qty(qty)
        self._repo.reserve_stock(sku, qty)

    def __call__(self, sku: str, qty: int) -> None:
        self.execute(sku, qty)
