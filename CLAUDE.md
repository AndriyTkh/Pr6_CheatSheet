# CheatSheet — Start Here

**Read this file at the start of every session (human or coding agent) before touching anything.**
It is the map. It tells you which doc is the source of truth for what, how to record progress, and the git rules that keep 5 people + coding agents from colliding.

CheatSheet is a **columnar, lineage-tracked compute graph over rows** — a spreadsheet on the surface, a build-system/DAG engine underneath — built as a 6-week pilot over Prozorro + YouControl (see `_docs/ARCHITECTURE.md §0`).

---

## 1. Read order (every session)

| Order | File | Read it for |
|-------|------|-------------|
| 1 | **`CLAUDE.md`** (this file) | The map, tracking rules, git rules. |
| 2 | **`_docs/ARCHITECTURE.md`** | **The technical contract.** All `§N` references in every doc point here. Architecture, data model, execution engine, recipes, security. Read the sections your task cites. |
| 3 | **`_docs/TASKS.md`** | Your role's task list + live progress tracking. Find your task, check its `Status`, check its `Depends on` is `DONE`. |
| 4 | **`_docs/repo-structure.md`** | Where your code lands — the folder skeleton, mapped to `ARCHITECTURE.md` sections. |
| 5 | **`_docs/tech-stack-decision.md`** | *Why* each tech pick (companion to ARCHITECTURE.md's *what*). Read when a choice surprises you. |
| ref | **`_docs/migrations/0001_core_schema.sql`** | **Locked schema contract.** Read-only for everyone except the backend/DB owner. Changed only via a new numbered migration + team agreement. |
| ref | **`_docs/archive/`** | Source briefs (owner brief, product vision, rough outline). Historical — `[owner-brief §N]` refs in TASKS.md point into `cheatsheet-owner-brief.md`. |

---

## 2. Doc map — what each file owns

Each fact has exactly one home. Don't restate a spec in another doc; link to it.

- **`_docs/ARCHITECTURE.md`** — the *what* and the *how* of the system. Canonical `§N` anchors. Change only by team agreement; it is the contract every recipe and route is built against.
- **`_docs/TASKS.md`** — the *who* and the *when*. Role-owned, week-ordered task lists, plus the live `Status` of each task. This is the only doc that changes daily.
- **`_docs/repo-structure.md`** — the *where*. Folder layout. Update when you add a real folder the skeleton didn't predict.
- **`_docs/tech-stack-decision.md`** — the *why* behind stack picks.
- **`_docs/migrations/0001_core_schema.sql`** — the *frozen data contract*. The ORM mirrors it, never the reverse.

If you rename or move any doc, fix its inbound references in the same commit (grep the old name across `_docs/` and `CLAUDE.md`).

---

## 3. Progress tracking

Status lives **inline in `_docs/TASKS.md`**, one `Status` line per task. That line is the single source of truth — there is no second tracker to keep in sync.

**Status tokens** (these map 1:1 to the Trello board columns):

| Token | Means | Trello column |
|-------|-------|---------------|
| `TODO` | not started | Backlog / This Week |
| `WIP` | in progress | In Progress |
| `BLOCKED` | waiting on a dependency or a decision | Blocked |
| `REVIEW` | done, in PR / awaiting handoff acceptance | Review/Handoff |
| `DONE` | merged + dependents unblocked | Done |

**How to update:** edit only the `  - **Status:** ...` line of the task you are on. Optionally append who + branch/PR:

```
  - **Status:** `WIP` @nazar role-2/schema-models
  - **Status:** `BLOCKED` waiting on Role 1 YouControl key
  - **Status:** `REVIEW` PR #14
  - **Status:** `DONE`
```

**Weekly gates are the heartbeat.** The gate table at the top of `TASKS.md` has a `Gate status` column (`PENDING` / `MET`), edited only by the coordinator. A week does not advance until its gate is `MET`. If you want one number for "how's the project doing," it's "which gates are `MET`."

**Blocked is a signal, not a dead end.** Set `BLOCKED` with the reason; the coordinator clears blockers (that column is theirs to watch).

---

## 4. Coding-agent workflow (per session)

1. Read `CLAUDE.md` → `_docs/ARCHITECTURE.md` (the sections your task cites) → your role's section in `_docs/TASKS.md`.
2. Pick a `TODO` task whose `Depends on` tasks are all `DONE`. If nothing is unblocked, say so — don't start blocked work.
3. Create a branch: **`role-<N>/<short-slug>`** (e.g. `role-2/dag-cycle-check`). Never commit work to `master` directly.
4. Set the task's `Status` to `WIP` on your branch.
5. Implement against the `§N` contract in `ARCHITECTURE.md`. If the spec is wrong or ambiguous, flag it — don't silently diverge; `ARCHITECTURE.md` is shared.
6. Set `Status` to `REVIEW`, open a PR (one task ≈ one PR — small, reviewable).
7. On merge, set `Status` to `DONE`. If your task was a handoff (a `Depends on` for someone else), tell that person their dependency is live.

---

## 5. Git — avoid conflicts

The tracking design is built so parallel work doesn't fight. Keep it that way:

- **Branch per task/role:** `role-<N>/<slug>`. Merge via PR. Never push tracking edits straight to `master`.
- **One editor per `Status` line.** Different tasks are different, non-adjacent lines → git auto-merges them. You only ever edit the status of the task you own.
- **Never reflow or reformat a doc you're not changing.** No editor "format on save" / rewrap on `ARCHITECTURE.md` or `TASKS.md` — turning a 1-line change into a whole-file diff is what manufactures conflicts. `.editorconfig` disables trailing-whitespace churn for markdown; leave it on.
- **`.gitattributes` pins `eol=lf`.** On Windows, do not let your editor re-save these files as CRLF — that alone can conflict every line. The config handles it; don't override.
- **Small PRs, merge often.** A task-sized PR merged daily rarely conflicts. A week-long mega-branch always does.
- **The schema is locked.** `0001_core_schema.sql` changes only via a *new* numbered migration + team agreement — never an in-place edit. Same for any shipped `recipe_version`.

---

## 6. Guardrails always in force (ARCHITECTURE.md §11)

- **Public data only.** Every document carries `external_ok`; un-attested sources are blocked from external providers, never silently sent.
- **Secrets server-side only.** Provider keys live behind one server proxy — never in the repo, client, or logs.
- **Isolation is structural.** A recipe never reaches outside the `row_context` the framework hands it.
