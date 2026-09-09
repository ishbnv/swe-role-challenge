"""Explicit local setup entrypoint; feature owners implement their initializers.

No host introspection or model discovery. Running this is a candidate setup action;
serving boot never creates schemas or seeds data. Reset uses Docker volume removal.
"""

from adapters.persistence_sqlalchemy.session import open_database
from apps.settings import database_url
from plugins.inventory.schema import initialize as initialize_inventory
from plugins.orders.schema import initialize as initialize_orders


def main() -> None:
    with open_database(database_url()) as resources:
        initialize_inventory(resources.session_factory)
        initialize_orders(resources.session_factory)
    print("schema ready")


if __name__ == "__main__":
    main()
