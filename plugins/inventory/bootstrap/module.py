"""Implement Inventory's declarations and assembly.

Declare owned operations, construct feature collaborators, bind handlers, and
contribute `stock <sku>`. The step declares SESSION_FACTORY and INVOKER as inputs.
Keep business behavior separate from assembly. Schema setup is an explicit action.
"""

from adapters.persistence_sqlalchemy.bootstrap import SESSION_FACTORY
from core.runtime_spi import INVOKER, BootContext, Command, Module, Step
from plugins.inventory.adapters.cli import make_stock_cli
from plugins.inventory.adapters.handlers import (
    make_reserve_stock_handler,
    make_stock_of_handler,
)
from plugins.inventory.application.use_cases import GetStockUseCase, ReserveStockUseCase
from plugins.inventory.infrastructure.repository import SqlAlchemyStockRepository
from plugins.inventory.public import RESERVE_STOCK, STOCK_OF


def _assemble(ctx: BootContext) -> None:
    session_factory = ctx.require(SESSION_FACTORY)
    invoker = ctx.require(INVOKER)

    repo = SqlAlchemyStockRepository(session_factory)
    get_stock_uc = GetStockUseCase(repo)
    reserve_stock_uc = ReserveStockUseCase(repo)

    ctx.bind(STOCK_OF, make_stock_of_handler(get_stock_uc))
    ctx.bind(RESERVE_STOCK, make_reserve_stock_handler(reserve_stock_uc))
    ctx.contribute(Command("stock", make_stock_cli(invoker)))


inventory_module = Module(
    name="inventory",
    steps=(
        Step(
            "inventory.assemble",
            _assemble,
            requires=frozenset({SESSION_FACTORY, INVOKER}),
        ),
    ),
    operations=frozenset({RESERVE_STOCK, STOCK_OF}),
)
