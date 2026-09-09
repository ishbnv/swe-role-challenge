"""Generic database resources. Host owns lifetime; plugins own rows and queries.

Each transaction creates/closes its own Session. Never share a live Session across
owners. The host must keep open_database active until all application work ends.
"""

from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.engine import URL
from sqlalchemy.orm import Session, sessionmaker

type SessionFactory = sessionmaker[Session]


@dataclass(frozen=True)
class DatabaseResources:
    engine: Engine
    session_factory: SessionFactory


@contextmanager
def open_database(url: str | URL) -> Generator[DatabaseResources]:
    """Check connectivity, yield resources, dispose the pool on every exit path.

    Disposal closes pooled connections, not leaked checked-out sessions. Callers must
    close their sessions, normally by using transaction or factory() as a context.
    An escaped engine can reconnect; resource lifetime is a host ownership rule.
    """
    engine = create_engine(url, pool_pre_ping=True, connect_args={"connect_timeout": 5})
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        yield DatabaseResources(
            engine=engine,
            session_factory=sessionmaker(engine, expire_on_commit=False),
        )
    finally:
        engine.dispose()


@contextmanager
def transaction(factory: SessionFactory) -> Generator[Session]:
    """Commit on success; roll back on exception; always close the owner session."""
    with factory.begin() as session:
        yield session
