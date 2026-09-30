"""Application service for Inventory operations."""

from plugins.inventory.application.ports import StockRepository
from plugins.inventory.application.use_cases import GetStockUseCase, ReserveStockUseCase


class InventoryService:
    def __init__(self, repository: StockRepository) -> None:
        self._get_stock = GetStockUseCase(repository)
        self._reserve_stock = ReserveStockUseCase(repository)

    def get_stock(self, sku: str) -> int:
        return self._get_stock.execute(sku)

    def reserve_stock(self, sku: str, qty: int) -> None:
        self._reserve_stock.execute(sku, qty)
