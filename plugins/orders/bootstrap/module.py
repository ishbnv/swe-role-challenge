"""Implement Orders' declarations and assembly.

Declare owned and used operations, construct feature collaborators, bind handlers,
and contribute `place <sku> <qty>` and `recent <sku> <limit>`. The step declares
SESSION_FACTORY and INVOKER as inputs. Keep business behavior separate from
assembly; no stock reservation happens during boot.
"""

from adapters.persistence_sqlalchemy.bootstrap import SESSION_FACTORY
from core.runtime_spi import INVOKER, BootContext, Module, Step
from plugins.inventory.public import RESERVE_STOCK
from plugins.orders.adapters.cli import create_place_command, create_recent_command
from plugins.orders.adapters.handlers import (
    create_place_order_handler,
    create_recent_orders_handler,
)
from plugins.orders.application.use_cases import GetRecentOrdersUseCase, PlaceOrderUseCase
from plugins.orders.infrastructure.inventory_client import InventoryStockReservationClient
from plugins.orders.infrastructure.repository import SqlAlchemyOrderRepository
from plugins.orders.public import (
    PLACE_ORDER,
    RECENT_ORDERS,
)


def _assemble(ctx: BootContext) -> None:
    session_factory = ctx.require(SESSION_FACTORY)
    invoker = ctx.require(INVOKER)

    repository = SqlAlchemyOrderRepository(session_factory)
    reservation_client = InventoryStockReservationClient(invoker)

    place_order_uc = PlaceOrderUseCase(repository, reservation_client)
    get_recent_orders_uc = GetRecentOrdersUseCase(repository)

    ctx.bind(
        PLACE_ORDER,
        create_place_order_handler(place_order_uc),
    )
    ctx.bind(
        RECENT_ORDERS,
        create_recent_orders_handler(get_recent_orders_uc),
    )

    ctx.contribute(create_place_command(invoker))
    ctx.contribute(create_recent_command(invoker))


orders_module = Module(
    name="orders",
    steps=(
        Step(
            "orders.assemble",
            _assemble,
            requires=frozenset({SESSION_FACTORY, INVOKER}),
        ),
    ),
    operations=frozenset({PLACE_ORDER, RECENT_ORDERS}),
    uses=frozenset({RESERVE_STOCK}),
)
