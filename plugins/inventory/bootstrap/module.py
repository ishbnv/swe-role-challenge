"""Implement Inventory's declarations and assembly.

Declare owned operations, construct feature collaborators, bind handlers, and
contribute `stock <sku>`. The step declares SESSION_FACTORY and INVOKER as inputs.
Keep business behavior separate from assembly. Schema setup is an explicit action.
"""

from adapters.persistence_sqlalchemy.bootstrap import SESSION_FACTORY
from core.runtime_spi import INVOKER, BootContext, Module, Step


def _assemble(ctx: BootContext) -> None:
    raise NotImplementedError("implement Inventory assembly")


inventory_module = Module(
    name="inventory",
    steps=(Step("inventory.assemble", _assemble, requires=frozenset({SESSION_FACTORY, INVOKER})),),
    operations=frozenset(),
)
