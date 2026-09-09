"""Executable composition root: select modules, assemble, run one CLI command.

Selection is editable for the optional extension. Host assembly/lifetime is frozen.
No schema creation or seeding occurs during boot.
"""

from collections.abc import Generator, Sequence
from contextlib import contextmanager

from sqlalchemy.engine import URL

from adapters.persistence_sqlalchemy.bootstrap import persistence_module
from adapters.persistence_sqlalchemy.session import open_database
from apps.cli import Cli
from apps.settings import database_url
from core.kernel.kernel import Kernel
from core.runtime_spi import Module
from plugins.inventory.module import inventory_module
from plugins.orders.module import orders_module

# Selection only: add an extension module import and tuple member here.
MODULES = (orders_module, inventory_module)


def build_cli(modules: Sequence[Module]) -> Cli:
    return Cli(Kernel().boot(modules).commands)


@contextmanager
def open_cli(
    modules: Sequence[Module] = MODULES, *, url: str | URL | None = None
) -> Generator[Cli]:
    """Own SQL resource lifetime, including cleanup when boot or a command fails."""
    with open_database(url if url is not None else database_url()) as resources:
        yield build_cli((*modules, persistence_module(resources)))
