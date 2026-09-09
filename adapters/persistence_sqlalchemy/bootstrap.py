"""Publish host-managed SQL resources through ordinary bootstrap artifacts.

This supplied module does not create tables, seed stock, discover models, or own
repositories. It has no feature imports and introduces no extra bootstrap stage.
"""

from sqlalchemy import Engine
from sqlalchemy.orm import sessionmaker

from adapters.persistence_sqlalchemy.session import DatabaseResources, SessionFactory
from core.runtime_spi import ArtifactKey, BootContext, Module, Step

DATABASE_ENGINE: ArtifactKey[Engine] = ArtifactKey("persistence.engine", Engine)
SESSION_FACTORY: ArtifactKey[SessionFactory] = ArtifactKey("persistence.sessions", sessionmaker)


def persistence_module(resources: DatabaseResources) -> Module:
    """Declare actual providers; they are not Kernel built-ins."""

    def provide(ctx: BootContext) -> None:
        ctx.provide(DATABASE_ENGINE, resources.engine)
        ctx.provide(SESSION_FACTORY, resources.session_factory)

    return Module(
        name="persistence.sqlalchemy",
        steps=(
            Step(
                "persistence.provide",
                provide,
                provides=frozenset({DATABASE_ENGINE, SESSION_FACTORY}),
            ),
        ),
    )
