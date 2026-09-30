"""Public operation handlers for Orders."""

from collections.abc import Callable

from plugins.orders.application.use_cases import GetRecentOrdersUseCase, PlaceOrderUseCase
from plugins.orders.public import OrderSummary, PlaceOrderInput, RecentOrdersInput


def create_place_order_handler(
    use_case: PlaceOrderUseCase,
) -> Callable[[PlaceOrderInput], None]:
    def handle_place_order(inp: PlaceOrderInput) -> None:
        use_case.execute(inp.sku, inp.qty)

    return handle_place_order


def create_recent_orders_handler(
    use_case: GetRecentOrdersUseCase,
) -> Callable[[RecentOrdersInput], tuple[OrderSummary, ...]]:
    def handle_recent_orders(inp: RecentOrdersInput) -> tuple[OrderSummary, ...]:
        return use_case.execute(inp.sku, inp.limit)

    return handle_recent_orders
