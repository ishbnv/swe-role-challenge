"""Implement Orders' declarations and assembly.

Declare owned and used operations, construct feature collaborators, bind handlers,
and contribute `place <sku> <qty>` and `recent <sku> <limit>`. The step declares
SESSION_FACTORY and INVOKER as inputs. Keep business behavior separate from
assembly; no stock reservation happens during boot.
"""

from adapters.persistence_sqlalchemy.bootstrap import SESSION_FACTORY
from core.runtime_spi import INVOKER, BootContext, Module, Step


def _assemble(ctx: BootContext) -> None:
    raise NotImplementedError("implement Orders assembly")


orders_module = Module(
    name="orders",
    steps=(Step("orders.assemble", _assemble, requires=frozenset({SESSION_FACTORY, INVOKER})),),
    operations=frozenset(),
    uses=frozenset(),
)
