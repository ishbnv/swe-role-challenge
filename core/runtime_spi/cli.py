"""Neutral CLI contributions; the executable host only consumes them."""

from collections.abc import Callable, Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class Command:
    """A feature-owned CLI contribution. Its handler calls public operations."""

    name: str
    run: Callable[[Sequence[str]], str]
