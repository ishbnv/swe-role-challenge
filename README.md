# Build a runtime for independent features

**Python 3.14 · PostgreSQL · any agent, LLM, or editor allowed**

Build a small runtime and two working features. **Inventory owns stock. Orders
owns order records.** We supply contracts, a generic CLI, and database connection
mechanics. You implement assembly, business behavior, and feature persistence.

We want to see working software, clear ownership, meaningful tests, and your
reasoning. Share your screen throughout: prompts, edits, commands, and review.
You are responsible for explaining the code you submit, including generated code.

## 1. What success looks like

Starting with a fresh database, perform explicit setup, then run each command
in a new process:

```text
$ stock A1
10
$ place A1 3
placed
$ stock A1
7
$ recent A1 5
3
```

These are commands of `uv run python main.py`, not standalone shell programs.
Restarting the application or repeating setup must preserve committed data.

### The ownership boundary

```text
                    Generic CLI
                   /           \
                 stock       place / recent
                   |              |
          Public operations through the runtime
                   |              |
             INVENTORY <------- ORDERS
             owns stock         owns orders
                   |              |
          inventory schema   orders schema
                   \              /
                     PostgreSQL
```

The arrow from Orders to Inventory is a reservation request through Inventory's
public operation. Each feature writes only its own data.

| Action | Required result |
| --- | --- |
| Initialize | Create each owner's schema/tables. Seed absent stock with `A1 = 10`. Repeated setup preserves existing data. |
| Reserve stock | A positive quantity within available stock reduces stock. Nonpositive quantities raise `ValueError`; insufficient stock raises the supplied `InsufficientStock`. Rejection changes nothing. |
| Place order | Reject nonpositive quantities. Request a stock reservation, then save an order only if it succeeds. A rejected reservation leaves both stock and orders unchanged. |
| Read stock | Return current committed stock through Inventory's public operation. Inventory must work without Orders installed. |
| Read recent orders | Filter by SKU, sort by descending integer order ID, and apply the limit **in SQL**. Return a tuple of the supplied `OrderSummary` records. Missing SKU returns an empty tuple. |

`recent A1 2` prints quantities newest first, such as `3,2`; no results produce an
empty string. Only `A1` needs write support. Choose and explain other unknown-SKU
behavior, limit validation, and CLI error wording.

Execution is synchronous and sequential. For the core build, assume saving an
order succeeds after reservation.

## 2. Use Clean Architecture within each feature

Keep business rules and application logic independent of the database, CLI,
runtime, and other features' implementations. Dependencies should point toward
business logic; external integrations should implement contracts owned by the
consuming feature. Keep construction and wiring separate from request behavior.

**Choose your own file layout and abstractions.** Preserve the supplied
entrypoints. During review, explain how your dependency direction and tests
demonstrate these boundaries. Folder names alone do not establish compliance.
No tests for layer names, folder structure, or import rules are required.

- **Each feature owns its implementation and data.** Access another feature only
  through its `public.py` contracts and public invocation. Never import its private
  code or access its tables, repositories, live sessions, or transactions.
- **Business logic works independently.** Rules and application orchestration
  must be testable without booting the runtime or connecting to PostgreSQL. They
  must not depend on the CLI, runtime, SQLAlchemy, or peer public contracts.
  Dependencies on external behavior must be explicit and replaceable in tests.
- **Keep responsibilities distinguishable.** Business decisions, persistence,
  public input/output adaptation, CLI handling, and construction/wiring should
  be independently understandable. Explain where each lives and why.
- **The host stays generic.** Features contribute their own operation handlers
  and CLI commands. The host selects modules and manages resources; it does not
  enumerate feature commands or construct feature business objects.
- **The runtime stays generic.** Kernel imports no features, host, or persistence
  implementations. Features import neutral runtime contracts, never the concrete
  Kernel or executable host. Public contracts contain no executable handlers and
  can be imported without loading the host, Kernel, or SQLAlchemy.
- **Requests enter through public operations.** CLI handlers invoke operations;
  operation handlers delegate to private feature behavior. Business objects and
  peer-private services must not become shared bootstrap artifacts.

A shared database and session factory do not transfer data ownership. Each
feature controls its own transaction; no cross-feature transaction is required.

## 3. What the runtime must do

Implement the supplied `Kernel.boot(modules)` contract:

```text
Module declarations
        |
        v
Validate everything --> Invalid? Fail before any setup executes.
        |
        v
Execute setup in artifact dependency order
        |               |
        |          provide values / bind handlers / contribute commands
        v
Check all declared operations have handlers
        |
        v
Return ready App --> invoke operations + expose immutable commands
```

The contracts describe **two different relationships**:

| Declaration | Meaning | Creates setup ordering? |
| --- | --- | --- |
| `Step.requires / provides` | A setup step needs a value produced by another step. | Yes |
| `Module.operations / uses` | A module owns an operation or expects its owner to be installed. | No |

For example, feature setup needs `SESSION_FACTORY` before constructing database
collaborators. Orders needs Inventory's operation to be available when requests
run, but Orders may bind its own handlers before Inventory does. Mutual operation
dependencies are legal; they do not create a setup cycle.

`INVOKER` is a runtime-provided artifact: inject its callable during setup, use it
after readiness. Every consumer must declare it in `requires` and obtain it with
`ctx.require(INVOKER)`. Do not inject or retain `BootContext` in request code.

<details>
<summary><strong>Exact runtime acceptance rules — use these when implementing and checking the Kernel</strong></summary>

| Point | Required behavior |
| --- | --- |
| Whole-plan validation | Before any setup, reject missing or duplicate artifact providers, artifact cycles, missing used operations, duplicate operation owners, and duplicate module or step names. Step names are globally unique. Validate independent steps too. |
| Identity | Keys and operations use object identity (`eq=False`): import the owner's constant. Reject distinct objects sharing a name across all declarations. Artifact and operation names are separate namespaces. |
| Artifact access | A step may read only its declared requirements and write only its declared outputs. Write each output once; all declared outputs must exist when the step returns. |
| Binding | A step may bind only operations owned by its module. Bind each operation once across all steps. Every declared operation must be bound before readiness. |
| Commands | Collect contributed commands; duplicate command names fail boot. |
| Successful boot | Disable retained contexts' `require/provide/bind/contribute`. Enable the invoker. Return an App with invocation and an immutable command tuple, without an artifact lookup API. |
| Failed boot | Return no App. Retained contexts and invokers must remain unusable. Arbitrary external side effects need not be undone. |
| Isolation | A Kernel can boot only once, including after failure. Fresh kernels have independent registries. The database intentionally persists. Unknown operations fail. |

Kernel is the sole provider of the exact `INVOKER` key. Make it available before
setup as an already-satisfied input; reject declarations providing it or using
another key named `runtime.invoker`. Invoker calls fail during boot and after
failed boot. `SESSION_FACTORY` is an ordinary adapter-provided artifact, not a
Kernel built-in.

Choose error classes and ordering among independent steps. `Module.uses` checks
installed availability; caller authorization is outside this exercise. Be ready
to explain your artifact storage and value-validation choices.

</details>

## 4. Database work you own

Implement each feature's `infrastructure/schema.initialize(factory)` through its
supplied export. Schema creation and seeding run via `apps.setup_db`, **never at
serving boot**. Use the supplied connection/session/transaction mechanics.
Ordinary commit/rollback and resource cleanup are required.

- Design each feature's tables and keys.
- Implement persistence and queries inside their owning features. SQLAlchemy
  ORM or Core is fine.

No migration framework, HTTP service, discovery system, extra lifecycle stages,
or production infrastructure is needed.

## 5. Starter map and edit boundaries

| Location | Your work |
| --- | --- |
| `core/kernel/kernel.py` | Implement runtime validation, planning, assembly, and readiness. |
| `plugins/{inventory,orders}/bootstrap/module.py` | Implement module declarations and feature assembly. |
| `plugins/{inventory,orders}/infrastructure/schema.py` | Implement owner schema initialization and seed. |
| New files inside each feature | Implement behavior, persistence, integrations, and CLI handling; choose their organization. |
| `tests/` (you create) | Design and implement your own tests and any fixtures they need. |
| `plugins/*/public.py` | Preserve existing contracts; additions allowed. |
| `apps/composition.py` | Change only feature module imports/selection for the optional extension. Preserve resource lifetime. |
| `pyproject.toml`, `uv.lock` | Tooling edits allowed; preserve Python 3.14, required dependencies, test discovery, and lint/type-checking rules. |

**Preserve all other supplied files**, including `core/runtime_spi/`, `adapters/`,
the generic host, launchers, Docker configuration, package markers, and
thin feature `module.py` / `schema.py` exports. Implement the stubs they call.
Do not weaken checks or hide real errors behind blanket ignores.

### Start and verify

Use the repository root as your working directory. You need `uv` and Docker with
Compose support. `uv sync` uses the Python version pinned in `.python-version`.
With Docker running:

```bash
uv sync --locked
docker compose up -d --wait
docker compose exec -T postgres psql -U interview -d plugin_runtime_interview -c 'SELECT 1;'
```

The SQL command checks database connectivity inside the container. Verify that
your Python application can connect using the supplied configuration too.

The starter imports successfully, but Kernel, feature assembly, and schema
initialization deliberately raise `NotImplementedError`. Implement those stubs
and the feature behavior before running the application examples below.

Application usage, after implementing the owner initializers and feature behavior:

```bash
uv run python -m apps.setup_db
uv run python main.py stock A1
uv run python main.py place A1 3
uv run python main.py stock A1
uv run python main.py recent A1 5
```

Tooling reference; choose your own development and verification workflow:

```bash
uv run pytest -q  # after writing your own tests
uv run ruff check .
uv run ruff format --check .
uv run basedpyright
```

Python is pinned to 3.14.6. PostgreSQL listens on `127.0.0.1:55479`. Keep test data
isolated from your demonstration data and make your tests repeatable. See
[database setup and reset instructions](adapters/persistence_sqlalchemy/README.md)
for connection details and port overrides.

## 6. Evidence to bring to the review

**No tests are supplied. Choosing what to verify is part of the exercise.** Write
your own automated tests and explain what they establish, why you chose those
cases, and what remains unverified. Your tests, lint, formatting, and type checks
should pass.

Bring convincing evidence of:

- A successful order and a rejected order, including the resulting stock and
  order records in PostgreSQL.
- Persistence across fresh application processes.
- Business behavior exercised without a database or runtime.
- Runtime behavior against the acceptance rules above.

Choose the test cases, organization, fixtures, and balance of isolated and
integration tests. Inspect stored state through its owner's test seam or public
API, never a peer's private storage. During review, we may ask you to predict and
run another case within the stated requirements.

Show persisted behavior across processes. Trace one
`place` request through your code: who decides, who calls whom, and who writes?
Explain one design tradeoff and one generated change you reviewed, if you used an
agent. State what is implemented, verified, or still incomplete.

### Optional extension: prove another feature can join

Add Replenishment with operation `replenishment.suggest` and CLI
`suggest <sku> <target>`. It owns the rule `max(0, target - current_stock)` and
obtains stock through Inventory's public `STOCK_OF`. No persistence is needed.

Choose its contracts and implementation. Add it through module selection without
changing Kernel, the host algorithm, or existing feature implementations. Test
all three modules in shuffled order through `open_cli` against an initialized
test database. After placing three units, `suggest A1 12` returns `5` and
`suggest A1 5` returns `0`. This extension is not required for core completion.

`open_cli` is the supplied context manager in `apps/composition.py`: it opens
database resources, boots the selected modules, and yields a `Cli` with
`run(argv)`. It accepts a `url` for your test database and cleans up resources on
exit. It does not initialize schemas or seed stock.
