# CheatSheet — Project Structure

Base skeleton, mapped to `ARCHITECTURE.md` components (§1, §15). Files are stubs — plumbing not implemented yet.

```
Pr6_CheatSheet/
├── migrations/
│   └── 0001_core_schema.sql      # §2 locked schema — frozen contract
│
├── backend/                      # Python + FastAPI (§15)
│   ├── pyproject.toml
│   ├── app/
│   │   ├── main.py                # FastAPI app entry
│   │   ├── core/                  # config, settings
│   │   ├── db/                    # SQLAlchemy async session
│   │   ├── models/                # ORM models mirroring migrations/0001
│   │   ├── schemas/                # Pydantic request/response + recipe output_schema
│   │   ├── api/routes/             # cases, rows, columns, cells, recipes, runs, documents, cross_row, eval
│   │   ├── dag/                    # §4 execution engine: cycle-check, topo-sort,
│   │   │                           #   wavefront-gated enqueue, cache_key, staleness/lineage walk
│   │   ├── tasks/                  # §4 Procrastinate app + cell-execution task (LISTEN/NOTIFY, SKIP LOCKED)
│   │   ├── recipes/                # §3/§6 recipe contract + catalog
│   │   │   ├── base.py             # Recipe contract (exec_type, input, params, output, exec, cite, eval)
│   │   │   ├── cell_producing/     # Connector(YouControl), Structured Extract, Web Search, Summarize,
│   │   │   │                       #   Classify/Score, Match & Verify, Aggregate/Fold, Compare/Diff, Custom Prompt
│   │   │   ├── row_producing/      # Connector(Prozorro), Manual upload, Generate/Seed rows
│   │   │   └── cross_row/          # Cross-row connect (candidate-gen + verify)
│   │   ├── connectors/             # §6a Prozorro + YouControl API clients
│   │   ├── documents/              # §7 docling ingest, OCR, chunking/embedding
│   │   ├── citations/              # §9 quote-locate anchoring, fuzzy OCR locate
│   │   ├── agents/                 # §8 bounded agent loops (Web Search, Match & Verify, cross-row verify)
│   │   ├── eval/                   # §12 per-recipe metrics + cell_feedback
│   │   └── realtime/               # §4 step7 SSE stream, batched flush, reconcile-on-reconnect
│   └── tests/
│
├── frontend/                      # React + TypeScript + Vite (§15)
│   ├── package.json
│   ├── vite.config.ts
│   ├── tsconfig.json
│   ├── index.html
│   └── src/
│       ├── main.tsx / App.tsx
│       ├── components/
│       │   ├── grid/               # §1 TanStack Table + virtual scroll, streaming cell updates
│       │   ├── citations/          # citation / verification view (§9)
│       │   └── recipes/            # recipe builder + Preview gate UI (§4 step4)
│       ├── hooks/                  # SSE stream hook, reconcile-on-reconnect
│       ├── api/                    # backend client
│       └── types/                  # shared TS types (mirrors backend schemas)
│
├── CLAUDE.md                     # start-here map, tracking + git rules (read every session)
├── .editorconfig / .gitattributes # LF + no-reflow — kill phantom merge conflicts
└── _docs/
    ├── ARCHITECTURE.md               # the technical contract (all §N point here)
    ├── TASKS.md                   # role-owned 6-week plan + live progress tracking
    ├── tech-stack-decision.md
    ├── repo-structure.md          # this file
    ├── migrations/0001_core_schema.sql   # §2 locked schema
    └── archive/                   # source briefs, historical
```

## Notes

- `_docs/migrations/0001_core_schema.sql` is the locked contract (§2) — backend `models/` must mirror it, never drift ahead of it.
- `dag/` and `tasks/` are split on purpose: `dag/` decides *when* a cell is ready (data-driven wavefront), `tasks/` (Procrastinate) decides *which worker* runs it (§4).
- `recipes/` subfolders mirror the three recipe shapes (§6) — same `exec()`/`cite`/`eval` contract across all three, enforced via `recipes/base.py`.
- Deferred features (Merge, Recursive/Expand walk, Assistant Plan/Auto, §13) have no folders yet — add them only when unblocked.
