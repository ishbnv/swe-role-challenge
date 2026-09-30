"""Application use cases for Orders."""

from plugins.orders.application.ports import OrderRepository, StockReservationPort
from plugins.orders.domain.order import validate_limit, validate_qty
from plugins.orders.public import OrderSummary


class PlaceOrderUseCase:
    def __init__(
        self,
        order_repo: OrderRepository,
        stock_reservation: StockReservationPort,
    ) -> None:
        self._order_repo = order_repo
        self._stock_reservation = stock_reservation

    def execute(self, sku: str, qty: int) -> int:
        validate_qty(qty)
        self._stock_reservation.reserve(sku, qty)
        return self._order_repo.save(sku, qty)

    def __call__(self, sku: str, qty: int) -> int:
        return self.execute(sku, qty)


class GetRecentOrdersUseCase:
    def __init__(self, order_repo: OrderRepository) -> None:
        self._order_repo = order_repo

    def execute(self, sku: str, limit: int) -> tuple[OrderSummary, ...]:
        validate_limit(limit)
        return self._order_repo.find_recent(sku, limit)

    def __call__(self, sku: str, limit: int) -> tuple[OrderSummary, ...]:
        return self.execute(sku, limit)
