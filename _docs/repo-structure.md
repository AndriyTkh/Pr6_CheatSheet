# CheatSheet — Project Structure

Base skeleton, mapped to `ARCHITECTURE.md` components (§1, §15).

```
Pr6_CheatSheet/
├── _docs/migrations/
│   ├── 0001_core_schema.sql      # §2 locked schema — frozen contract
│   └── 0002_sheets_and_lot_grain.sql  # §2a sheets, lot grain, list gate flags
│
├── backend/                      # Python + FastAPI (§15)
│   ├── pyproject.toml            # fastapi, uvicorn, sqlalchemy[asyncio], asyncpg,
│   │                             # pgvector, pydantic-settings, fastapi-users,
│   │                             # httpx (§6a), jsonschema (§3 output enforcement)
│   ├── docker-compose.yml        # local Postgres 15 + pgcrypto/vector
│   ├── scripts/
│   │   └── apply_migrations.py   # runs 0001 then 0002 against $DATABASE_URL
│   ├── CLAUDE.md                 # backend-tree conventions + run commands (auto-loaded here)
│   └── app/
│       ├── main.py               # FastAPI entrypoint
│       ├── core/config.py        # §15 settings — every secret from env
│       ├── db/                   # base.py (DeclarativeBase) + session.py (async)
│       ├── models/               # §2/§2a ORM mirror of 0001+0002 — never the reverse
│       │   ├── enums.py          # §5 statuses + the terminal/void/needs-human sets
│       │   ├── types.py          # shared PG enum + uuid_pk column helpers
│       │   ├── case.py sheet.py column.py cell.py document.py
│       │   ├── recipe.py         # recipe catalog + §10 run log
│       │   └── cross_row.py      # §8 signals with no single-row home
│       ├── dag/                  # §4 — when a cell is ready
│       │   ├── graph.py          # pure: cycle check, topo sort, up/downstream
│       │   ├── validation.py     # edge-add gate (§4 step2): cycle + §2a list/grain
│       │   ├── invariants.py     # §2 app-side invariants 2–4 (sheet/grain/expand)
│       │   └── errors.py         # journalist-readable rejections
│       ├── recipes/              # §3 contract + §6 catalog
│       │   ├── base.py           # Recipe / CellRecipe / RowProducingRecipe / CrossRowRecipe
│       │   ├── registry.py       # recipe slug ↔ (uuid, version) in the `recipe` table
│       │   ├── row_producing/    # prozorro_lots.py (§6a) — Expand/Pair builder wk3
│       │   ├── cell_producing/   # Structured Extract, Summarize, … (Roles 3/4)
│       │   └── cross_row/        # §8
│       ├── connectors/           # §6a — prozorro.py; youcontrol.py behind a key proxy
│       ├── services/             # orchestration the routes/queue call
│       │   └── row_ingest.py     # row-producing run → rows + cells (week-1 gate)
│       ├── api/routes/           # §15 — health.py; grid routes wk2
│       ├── schemas/              # pydantic request/response shapes
│       └── tests/                # pure tests always run; DB tests skip without
│                                 # CS_TEST_DATABASE_URL
│
├── frontend/                     # React + TypeScript + Vite (§15)
│   ├── CLAUDE.md                 # frontend-tree conventions + run commands (auto-loaded here)
│   ├── package.json
│   ├── vite.config.ts
│   ├── tsconfig.json
│   ├── index.html
│   └── src/
│       ├── main.tsx / App.tsx
│       ├── components/
│       │   ├── grid/             # §1 TanStack Table + virtual scroll, streaming cell updates
│       │   ├── citations/        # citation / verification view (§9)
│       │   └── recipes/          # recipe builder + Preview gate UI (§4 step4)
│       ├── hooks/                # SSE stream hook, reconcile-on-reconnect
│       ├── api/                  # backend client
│       └── types/                # shared TS types (mirrors backend schemas)
│
├── CLAUDE.md                     # start-here map, tracking + git rules (read every session)
├── .editorconfig / .gitattributes # LF + no-reflow — kill phantom merge conflicts
├── .claude/                      # checked-in harness config — team-shared, not personal
│   ├── settings.json             # allow-only permissions (git read-only, pytest, ruff,
│   │                             # npm run build, migrations) + the hook below
│   └── hooks/
│       └── verify-backend.sh     # PostToolUse: ruff --fix + backend suite on edited
│                                 # backend/*.py; silent elsewhere and without a venv
└── _docs/
    ├── ARCHITECTURE.md               # the technical contract (all §N point here)
    ├── architecture-index.md     # §N → line range, so agents read sections not the whole file
    ├── TASKS.md                  # the index: weekly gates, people, tracking + Verify rules
    ├── tasks/                    # the per-role task lists — the docs that change daily
    │   └── role-1.md role-2.md role-3-4.md role-5.md   # one file per role; edit only yours
    ├── handoffs/                 # one file per branch: dead ends, seams, doubts; deleted on merge
    ├── agentic-workflow-improvements.md  # workflow ideas NOT adopted + what would revive them
    ├── tech-stack-decision.md
    ├── repo-structure.md         # this file
    ├── migrations/               # the locked schema — 0001 + 0002, listed at the top of this tree
    └── archive/                  # source briefs + superseded docs, historical (read-only)
        ├── TASKS-backend.md      # ← superseded by _docs/tasks/role-2.md
        └── desired-workflow.md   # the pilot journalist workflow; ARCHITECTURE.md still cites its §N
```

## Directories to add later (in order)

| Directory            | What                                        | When                                     |
| -------------------- | ------------------------------------------- | ---------------------------------------- |
| `backend/app/tasks/` | Procrastinate queue wiring — worker + jobs   | Week 2, when runs stop being synchronous |
| `_docs/migrations/`  | The next numbered migration (`0003_…`)       | Only when schema changes — never in place |

## Notes

- `_docs/migrations/0001_core_schema.sql` + `0002_sheets_and_lot_grain.sql` are the locked contract (§2, §2a) — backend `models/` must mirror them, never drift ahead of them, and neither file is ever edited in place (`CLAUDE.md §5`).
- `_docs/archive/` is where superseded docs go — moved, not deleted, with a header saying what replaced them. A doc that still describes live work belongs in `_docs/`; two files describing the same live work is the failure mode (`CLAUDE.md §3`: one `Status` line, one source of truth).
- `backend/app/dag/` and `backend/app/tasks/` are split on purpose: `dag/` decides _when_ a cell is ready (data-driven wavefront), `tasks/` (Procrastinate) decides _which worker_ runs it (§4). Unrelated to `_docs/tasks/`, which holds the per-role plans.
- `recipes/` subfolders mirror the three recipe shapes (§6) — same `exec()`/`cite`/`eval` contract across all three, enforced via `recipes/base.py`.
- Deferred features (Merge, Recursive/Expand walk, Assistant Plan/Auto, §13) have no folders yet — add them only when unblocked.
