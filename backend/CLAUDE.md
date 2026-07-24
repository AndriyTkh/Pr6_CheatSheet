# backend/ — working rules

Loaded on top of the repo-root `CLAUDE.md` when you're working in this tree. Root file owns the map, tracking, git and delegation rules; this file owns backend conventions only. The contract is still `_docs/ARCHITECTURE.md` — read the sections your task cites via `_docs/architecture-index.md`, not the whole file.

Tasks: `_docs/tasks/role-2.md` (engine/API/schema) and `_docs/tasks/role-3-4.md` (recipes, documents, agents).

## Run it

```
cd backend
.venv/Scripts/Activate.ps1          # PowerShell; source .venv/bin/activate on POSIX
pytest -q                           # pure tests always run
$env:CHEATSHEET_DB_PORT = "55432"   # only if something already owns host 5432
docker compose up -d                # local Postgres 16 + pgcrypto/vector
python scripts/apply_migrations.py  # 0001 then 0002 against $CS_DATABASE_URL
python scripts/apply_queue_schema.py # Procrastinate's own tables (§4) — not one of ours
CS_TEST_DATABASE_URL=postgresql+asyncpg://cheatsheet:cheatsheet@127.0.0.1:55432/cheatsheet pytest -q
ruff check app                      # line-length 90
```

Two host-specific things that cost a session each if you get them wrong:

- **`127.0.0.1`, never `localhost`.** `localhost` resolves `::1` first and Docker's IPv6 publish black-holes the connect for ~21s before falling back — the suite looks hung, not broken.
- **`CHEATSHEET_DB_PORT`** shifts only the *host* side of the publish (`${CHEATSHEET_DB_PORT:-5432}:5432`). Use it when a native Postgres already owns 5432 rather than stopping that service; the container port never moves, so only the URL changes.

Pipe long runs to a file (`pytest -q > out.txt`), don't `| tail` — tail buffers to EOF, so you watch a blank screen for the whole run.

DB-backed tests **skip silently** without `CS_TEST_DATABASE_URL`. A skipped test is not a passed test — set the URL before claiming a DB task verified (`_docs/TASKS.md` "Verify").

## Non-negotiables

- **The migrations are the contract.** `_docs/migrations/0001_core_schema.sql` + `0002_sheets_and_lot_grain.sql` are locked. `models/` mirrors them — never the reverse. No field in a model that isn't in a migration. Schema changes = a *new* numbered migration + team agreement, never an in-place edit (root `CLAUDE.md §5`).
- **Four app-side invariants** (§2) the schema deliberately doesn't encode — they live in `dag/invariants.py` and must stay covered by tests: cell's row and column agree on `sheet_id`; a cell exists only where `row.depth == column.target_depth`; `inline` children share the parent's sheet; `new_table` children get a new one.
- **Edge-add is where things get rejected** (§4 step 2, §2a): cycle, `per_item` against a `value_type='list'` column, grain mismatch. Reject before any cell is created, anything enqueued, or anything spent. A runtime rejection is a bug — it means money moved.
- **Statuses are typed, eight of them** (§5). `NotApplicable` ≠ `InsufficientData` ≠ `NotFound`. Never downgrade one into another to make a code path simpler; the distinction is what the journalist reads.
- **Rejections are journalist-readable.** `dag/errors.py` — name the column and the fix, not the invariant's internal name.
- **No LLM where code will do** (§3). Connector extraction, counts, matches, arithmetic: deterministic. If you reach for a model to do arithmetic, stop.
- **Secrets from env only** (`core/config.py`, §11). Never hardcoded, never in a log record, never returned in a response. Provider keys sit behind one server-side proxy.
- **`cell.status` is data/display, never a lock.** Concurrency is Procrastinate + `LISTEN/NOTIFY` + `SKIP LOCKED` (§4). Do not hand-roll a poller.

## Layout (mirrors `_docs/repo-structure.md`)

| Dir | Owns |
|---|---|
| `models/` | §2/§2a ORM mirror of the migrations. `enums.py` holds the §5 status sets. |
| `dag/` | *When* a cell is ready: `graph.py` (pure — cycle, topo), `validation.py` (edge-add gate), `invariants.py`, `errors.py`. |
| `tasks/` | *Which worker* runs it (Procrastinate). Kept separate from `dag/` on purpose. |
| `recipes/` | §3 contract (`base.py`) + §6 catalog, split `row_producing/` · `cell_producing/` · `cross_row/`. |
| `connectors/` | §6a — `prozorro.py` (public), `youcontrol.py` (behind the key proxy). |
| `services/` | Orchestration the routes and the queue both call. |
| `api/routes/` | HTTP surface; scope grid routes by `sheet_id`, never one-grid-per-case. |
| `tests/` | Pure tests always run; DB tests behind `requires_db`. |

## Writing a recipe

Everything goes through `recipes/base.py` — same `exec()`/`cite`/`eval` contract across all three shapes. Declare inputs `required`/`optional` **and** `whole_list`/`per_item` (§2a/§3); `output_schema` is enforced server-side, so bad model JSON becomes `Error`/`NeedsReview`, never a silently malformed value. A recipe reads `row_context` and nothing outside it (§11 isolation). Citations are located by string-searching the verbatim quote back into the source — a model-reported page number is never trusted (§9).

## Tests

Name the file after the thing, mirroring the `Verify` line in your task file. Recipe tests stub the provider — a test that hits a live LLM or YouControl is a bill, not a verification. For cost-safety features (dead-end lock, `external_ok` gate, idempotency), assert with a spy that the provider call **did not happen**; asserting on the returned status alone doesn't prove the money was saved.
