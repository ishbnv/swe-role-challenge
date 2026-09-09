"""Implement Inventory's explicit schema initialization.

Create Inventory's schema and tables. Initialize A1 = 10 only when absent;
repeated setup must preserve existing stock. Serving boot does not run this code.
"""

from adapters.persistence_sqlalchemy.session import SessionFactory


def initialize(factory: SessionFactory) -> None:
    raise NotImplementedError("initialize inventory schema")
