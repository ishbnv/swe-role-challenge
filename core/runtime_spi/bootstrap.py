"""Setup declarations and step-scoped assembly access."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol

from core.runtime_spi.artifacts import ArtifactKey
from core.runtime_spi.cli import Command
from core.runtime_spi.operations import Operation


class BootContext(Protocol):
    """Step-scoped assembly access; no business code may retain this context."""

    def require[T](self, key: ArtifactKey[T]) -> T: ...
    def provide[T](self, key: ArtifactKey[T], value: T) -> None: ...
    def bind[I, O](self, operation: Operation[I, O], handler: Callable[[I], O]) -> None: ...
    def contribute(self, command: Command) -> None: ...


@dataclass(frozen=True)
class Step:
    """A graph node. Only artifact requires/provides create ordering edges."""

    name: str
    run: Callable[[BootContext], None]
    requires: frozenset[ArtifactKey[Any]] = frozenset()
    provides: frozenset[ArtifactKey[Any]] = frozenset()


@dataclass(frozen=True)
class Module:
    """Feature-owned declarations; operations/uses are catalog checks, not edges."""

    name: str
    steps: tuple[Step, ...]
    operations: frozenset[Operation[Any, Any]] = frozenset()
    uses: frozenset[Operation[Any, Any]] = frozenset()
