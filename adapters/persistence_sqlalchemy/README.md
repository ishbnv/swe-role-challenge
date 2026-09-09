# Supplied PostgreSQL infrastructure

This package is working infrastructure. It owns engine/session construction,
transaction mechanics and resource bootstrap declarations. It owns **no feature
rows, tables, repositories, schema migrations or query language**.

| API | Use |
| --- | --- |
| `open_database(url)` | Host context manager: check connection, yield `DatabaseResources`, dispose pool on exit (including failed boot). |
| `resources.session_factory` | Creates separate SQLAlchemy Sessions for owner-local work. |
| `transaction(factory)` | Session context manager: commit success, roll back exceptions (including commit failures), always close session. |
| `persistence_module(resources)` | Supplies declared `DATABASE_ENGINE` and `SESSION_FACTORY` artifacts. No table discovery or DDL. |

Feature composition declares `SESSION_FACTORY` in its step's `requires` and uses
`ctx.require(SESSION_FACTORY)`. Construct that feature's repository/UoW adapters with
it. SQLAlchemy imports belong in feature infrastructure/setup, not pure business or
application code. The factory may be shared; a live Session/transaction or another
owner's tables may not be shared across Orders/Inventory. Application code sees
owner-defined ports, not this infrastructure API.

A generic adapter transaction looks like this (no feature model is provided):

```python
from adapters.persistence_sqlalchemy.session import transaction

with transaction(factory) as session:
    # Execute owner-local SQLAlchemy work here.
    ...
```

`apps.composition.open_cli` owns the database context around both boot and commands.
`build_cli` itself remains generic and accepts modules; it does not create resources.
Dispose closes idle pooled connections; it is not a sandbox and cannot close leaked
checked-out Sessions. Close every owner session before leaving the host context.
Do not retain the CLI/resources beyond their context manager lifetime.

## Local Docker database

From the repository root, with `uv` installed and Docker running:

```bash
uv sync --locked
docker compose up -d --wait
docker compose exec -T postgres psql -U interview -d plugin_runtime_interview -c 'SELECT 1;'
uv run ruff check .
uv run ruff format --check .
uv run basedpyright
```

The Compose project is `plugin-runtime-interview-20260909`, service `postgres`,
volume `interview_pgdata` within that project. No fixed global container name is
used. PostgreSQL 17 is published only on `127.0.0.1:55479`. Credentials are deliberately
local/disposable: database `plugin_runtime_interview`, user `interview`, password
`interview_local_only`. These are not production settings.

If that port is occupied, leave the other service alone and set an unused port in
the same shell **before both Compose and Python**:

```bash
export INTERVIEW_PG_PORT=55480
docker compose up -d --wait
```

`apps/settings.py` selects `postgresql+psycopg` and the same port. Use this supplied
local database; no external database or production credentials are needed.

## Candidate schema work

Implement `initialize(factory)` in each feature's `infrastructure/schema.py`.
The feature-root `schema.py` files are supplied re-exports; preserve them.
Each initializer creates only its owner's schema (`inventory` or `orders`) and
tables. Table design is yours. Inventory inserts seed A1=10 only when absent.
Repeated initialization must preserve stock and order history. Then run explicitly:

```bash
uv run python -m apps.setup_db
uv run python main.py stock A1
uv run python main.py place A1 3
uv run python main.py recent A1 5
```

`apps.setup_db` calls the two owner initializers explicitly. They raise
`NotImplementedError` until implemented. Boot never runs schema setup or resets
stock. A migration framework is not required.

Stop without losing data:

```bash
docker compose stop
```

Reset **only this disposable project's database volume** (erases interview data):

```bash
docker compose down -v
docker compose up -d --wait
uv run python -m apps.setup_db
```

Use these commands from this candidate directory, with its Compose project name.
Do not use Docker prune or reset an unrelated database.

## Tests and isolation

No tests or fixtures are supplied. Write your own tests and choose how to isolate
their data from the working demonstration database. The local Compose role can
create separate test databases. Any cleanup must affect only data or databases
created by your tests. Keep the suite repeatable.

The `SELECT 1` command above checks connectivity inside the database container;
also verify Python connectivity through the supplied configuration. It does not
validate feature behavior or replace your tests.

```bash
uv run pytest -q  # after writing your own tests and fixtures
```

Implementation follows SQLAlchemy's documented
[session transaction context](https://docs.sqlalchemy.org/en/20/orm/session_basics.html#using-a-sessionmaker)
and [engine disposal](https://docs.sqlalchemy.org/en/20/core/connections.html#engine-disposal).
