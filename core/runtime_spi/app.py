"""The ready runtime surface; bootstrap artifacts are not exposed here."""

from typing import Protocol

from core.runtime_spi.cli import Command
from core.runtime_spi.operations import Operation


class App(Protocol):
    """Ready runtime: public invocation plus an immutable command collection."""

    @property
    def commands(self) -> tuple[Command, ...]: ...

    def invoke[I, O](self, operation: Operation[I, O], input: I) -> O: ...
