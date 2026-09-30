"""Stock reservation client adapter implementing StockReservationPort."""

from core.runtime_spi import Invoker
from plugins.inventory.public import RESERVE_STOCK, ReserveStockInput
from plugins.orders.application.ports import StockReservationPort


class InventoryStockReservationClient(StockReservationPort):
    def __init__(self, invoker: Invoker) -> None:
        self._invoker = invoker

    def reserve(self, sku: str, qty: int) -> None:
        self._invoker(RESERVE_STOCK, ReserveStockInput(sku=sku, qty=qty))
