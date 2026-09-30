"""Application service facade for Orders orchestration."""

from plugins.orders.application.ports import OrderRepository, StockReservationPort
from plugins.orders.application.use_cases import GetRecentOrdersUseCase, PlaceOrderUseCase
from plugins.orders.public import OrderSummary


class OrdersService:
    def __init__(
        self,
        repository: OrderRepository,
        reservation_port: StockReservationPort,
    ) -> None:
        self._place_order_uc = PlaceOrderUseCase(repository, reservation_port)
        self._get_recent_orders_uc = GetRecentOrdersUseCase(repository)

    def place_order(self, sku: str, qty: int) -> int:
        return self._place_order_uc.execute(sku, qty)

    def recent_orders(self, sku: str, limit: int) -> tuple[OrderSummary, ...]:
        return self._get_recent_orders_uc.execute(sku, limit)
