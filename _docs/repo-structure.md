# CheatSheet — Project Structure

Base skeleton, mapped to `ARCHITECTURE.md` components (§1, §15).

```
Pr6_CheatSheet/
├── _docs/migrations/
│   └── 0001_core_schema.sql      # §2 locked schema — frozen contract
│
├── backend/                      # Python + FastAPI (§15)
│   ├── pyproject.toml            # 6 deps: fastapi, uvicorn, sqlalchemy, asyncpg, pydantic-settings, fastapi-users
│   └── app/
│       ├── main.py               # FastAPI app entry
│       ├── core/
│       │   └── config.py         # pydantic-settings (DB URL, API keys from env)
│       ├── db/
│       │   ├── base.py           # DeclarativeBase + TimestampMixin + VersionMixin
│       │   └── session.py        # Async engine + get_db() dependency
│       │
│       ├── models/               # — ORM models mirroring migrations/0001 go here
│       ├── schemas/              # — Pydantic request/response schemas go here
│       ├── api/routes/           # — endpoint files go here
│       ├── recipes/              # — §3/§6 recipe contract + catalog goes here
│       └── tests/                # — test fixtures go here
│
├── frontend/                     # React + TypeScript + Vite (§15)
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
└── _docs/
    ├── ARCHITECTURE.md               # the technical contract (all §N point here)
    ├── TASKS.md                   # role-owned 4-week (+buffer) plan + live progress tracking
    ├── tech-stack-decision.md
    ├── repo-structure.md         # this file
    ├── migrations/0001_core_schema.sql   # §2 locked schema
    └── archive/                  # source briefs, historical
```

## Directories to add later (in order)

| Directory                     | What                                           | When                             |
| ----------------------------- | ---------------------------------------------- | -------------------------------- |
| `backend/app/models/`         | ORM models per table                           | First route needs DB queries     |
| `backend/app/schemas/`        | Pydantic request/response models               | Same time as models              |
| `backend/app/api/routes/`     | CRUD endpoints (cases, rows, cells, etc.)      | Add route = add file             |
| `backend/app/recipes/base.py` | Recipe abstract class (§3)                     | Before DS team writes recipes    |
| `backend/app/dag/`            | Cycle check, topo-sort, wavefront enqueue (§4) | Before any column execution      |
| `backend/app/tasks/`          | Procrastinate job queue (§4)                   | When background execution starts |
| `backend/app/connectors/`     | Prozorro + YouControl API clients (§6a)        | When connectors are built        |
| `backend/app/documents/`      | Docling ingest, OCR, chunking (§7)             | When doc processing starts       |
| `backend/app/citations/`      | Quote→locate anchoring, fuzzy OCR (§9)         | With documents                   |
| `backend/app/agents/`         | Bounded agent loops (§8)                       | With agentic recipes             |
| `backend/app/eval/`           | Per-recipe metrics + cell_feedback (§12)       | With eval tracking               |
| `backend/app/realtime/`       | SSE streaming, reconcile-on-reconnect (§4)     | When frontend needs live updates |
| `migrations/`                 | Alembic / numbered migration files             | Only when schema changes         |

## Notes

- `_docs/migrations/0001_core_schema.sql` is the locked contract (§2) — backend `models/` must mirror it, never drift ahead of it.
- `dag/` and `tasks/` are split on purpose: `dag/` decides _when_ a cell is ready (data-driven wavefront), `tasks/` (Procrastinate) decides _which worker_ runs it (§4).
- `recipes/` subfolders mirror the three recipe shapes (§6) — same `exec()`/`cite`/`eval` contract across all three, enforced via `recipes/base.py`.
- Deferred features (Merge, Recursive/Expand walk, Assistant Plan/Auto, §13) have no folders yet — add them only when unblocked.
