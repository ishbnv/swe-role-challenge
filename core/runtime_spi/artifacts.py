"""Typed bootstrap artifact identities; values exist only within one runtime."""

from dataclasses import dataclass


@dataclass(frozen=True, eq=False)
class ArtifactKey[T]:
    """Bootstrap-only value identity. Import the owner's constant to reference it."""

    name: str
    shape: type[T]
