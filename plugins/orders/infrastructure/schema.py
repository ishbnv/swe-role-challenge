"""Implement Orders' explicit schema initialization.

Create Orders' schema and tables, preserving existing order history on repeated
setup. Inventory's data is not owned here. Serving boot does not run this code.
"""

from adapters.persistence_sqlalchemy.session import SessionFactory


def initialize(factory: SessionFactory) -> None:
    raise NotImplementedError("initialize orders schema")
