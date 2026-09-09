"""YOURS: validate declarations, plan artifact steps, assemble, verify, freeze.

Kernel is single-use. boot(modules) returns App only after complete success.
The implementation must know no feature or executable host. Kernel alone supplies
the built-in INVOKER artifact as an already-satisfied planning input; its per-boot
callable must remain disabled until readiness and after failed boot.
"""

from collections.abc import Sequence

from core.runtime_spi import App, Module


class Kernel:
    def boot(self, modules: Sequence[Module]) -> App:
        raise NotImplementedError("implement runtime assembly")
