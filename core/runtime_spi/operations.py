"""Public operation identities and the runtime-owned invocation dependency."""

from dataclasses import dataclass
from typing import Protocol

from core.runtime_spi.artifacts import ArtifactKey


@dataclass(frozen=True, eq=False)
class Operation[I, O]:
    """Public behavior identity; availability is separate from startup ordering."""

    name: str
    input: type[I]
    output: type[O]


class Invoker(Protocol):
    """Usable only once boot succeeds. Adapters receive this, not BootContext."""

    def __call__[I, O](self, operation: Operation[I, O], input: I) -> O: ...


# Kernel is the sole provider. Steps must explicitly require this exact key.
# The value is available for injection during assembly, but calls wait for READY.
INVOKER: ArtifactKey[Invoker] = ArtifactKey("runtime.invoker", Invoker)
