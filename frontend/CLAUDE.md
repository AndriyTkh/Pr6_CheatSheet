# frontend/ — working rules

Loaded on top of the repo-root `CLAUDE.md` when you're working in this tree. Root file owns the map, tracking, git and delegation rules; this file owns frontend conventions only. The contract is `_docs/ARCHITECTURE.md` — read the sections your task cites via `_docs/architecture-index.md` (§1, §2a, §4 step 7, §5, §9, §15 are the ones that matter here).

Tasks: `_docs/tasks/role-5.md`.

## Run it

```
cd frontend
npm install
npm run dev      # vite
npm run build    # tsc -b && vite build — this is the machine half of every Verify line
```

There is no test runner in the pilot stack. `npm run build` must be clean, and each task in `role-5.md` names the one manual check that actually proves the behaviour. Do both before `REVIEW`. If a manual check keeps costing more than a test would, say so — adding vitest is a proposal, not a silent decision.

## Non-negotiables

- **Types are generated, not hand-written.** `types/` comes from Role 2's OpenAPI spec (`openapi-typescript`). If the backend shape changed, regenerate — never patch the local type to make the build pass. A regenerated diff that breaks the build is the mechanism working.
- **A case is a set of sheets** (§2a), not one grid. Never assume one grid per case; scope rows/columns/cells by `sheet_id`, and keep per-sheet sort/filter state.
- **Eight terminal statuses, visually distinct** (§5). `NotApplicable` ("nothing to check") must not read like `InsufficientData` ("couldn't find"). Don't collapse the set into done/error.
- **Nothing runs without an explicit confirm.** Preview → user confirms → full run (§4 step 4). Stale columns grey out and wait; never auto-rerun (§4 "Staleness").
- **Surface the §2a list-gate rejection properly** — name the column and offer both Expand modes. A generic error here is a bug: it's the moment the product teaches the user its core concept.
- **Citations are per item, not per cell.** `citation_jsonb` is an array aligned to `value_jsonb` — a list cell has one citation per item (§9, §2a).
- **Render list cells as lists** — count/preview of items, never a joined string.
- **No secrets, ever.** Provider keys are server-side only (§11). If a feature seems to need a key in the client, it needs a backend route instead.

## Performance rules (this is the product, not polish)

Pilot scale is ~10–15k cells per case, filling live. So:

- Virtualized grid (TanStack Table + `@tanstack/react-virtual`). Never render the full row set.
- SSE updates arrive **batched** from the backend (150–250ms windows). Apply them so only touched cells re-render — check with the React Profiler, not by eye.
- Reconnect calls `?since=<version>` **before** resuming the stream, so nothing is silently lost.
- Rowspan under virtualization is a known week-1 risk (§1) — the spike's written decision governs how `inline` Expand renders. Don't design against an untested assumption.

## Layout (mirrors `_docs/repo-structure.md`)

| Dir | Owns |
|---|---|
| `components/grid/` | §1 table + virtual scroll, streaming cell updates, sort/filter, sheet switcher. |
| `components/citations/` | §9 source/verification view. |
| `components/recipes/` | Recipe builder + Preview gate (§4 step 4). |
| `hooks/` | SSE stream hook, reconcile-on-reconnect. |
| `api/` | Backend client. |
| `types/` | Generated from OpenAPI — do not hand-edit. |
