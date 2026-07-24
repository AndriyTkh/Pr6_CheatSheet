# CheatSheet — Project Task Plan (index)

**Purpose:** split the pilot — **4-week build + 1.5-week buffer** (compressed from the original 6-week plan, tighter external deadline; ARCHITECTURE.md §14/§14a) — into role-owned task lists. One file per person/pair, ordered by week, each task self-contained (what to do, what you need first, what you hand off, how to prove it's done, where to read details, and when it's due).

**rev. 3 of this doc:** the per-role task lists moved out of this file into `_docs/tasks/role-*.md`, and every code task gained a runnable `Verify` line. Nothing else changed — task text, statuses, and target dates carried over verbatim. Rationale + the ideas not adopted: `_docs/agentic-workflow-improvements.md`.

**rev. 2:** re-synced to ARCHITECTURE.md rev. 3/4 — lot grain, sheets, the expansion gate, `NotApplicable`, migration `0002`, and the Expand/Pair builder/Formula-Compute/Start recipes are now tasked. Schedule compressed 6→4 weeks + buffer; every task gets a **Target date**, computed forward from kickoff (2026-07-22).

---

## Task lists — read only yours

| Role | File | Owns |
|------|------|------|
| 1 | `_docs/tasks/role-1.md` | Coordinator — legal, data & stakeholder liaison |
| 2 | `_docs/tasks/role-2.md` | Backend / DB developer |
| 3 & 4 | `_docs/tasks/role-3-4.md` | Data Science / Agentic developers (shared list, `[Track A]`/`[Track B]` tags) |
| 5 | `_docs/tasks/role-5.md` | Frontend developer/designer |

Read this index once for the gates and the rules, then work in your role file only. **Never open all four** — that's the context cost this split exists to remove. If you need someone else's status, ask them or read the one task, not the file.

---

## Source docs

Read before starting, and whenever a task references a `§`:

- `_docs/ARCHITECTURE.md` — **the** technical contract. All `§N` references point here unless marked `[owner-brief §N]`. `§14`/`§14a` is the build-order + buffer these weeks are dated against. Use `_docs/architecture-index.md` to read only the sections your task cites.
- `_docs/archive/drive/Briefs & Vision/cheatsheet-owner-brief.md` — product/PM brief (Ukrainian), acceptance criteria, canonical user scenario (§5), demo contract (§13). Its own "week N" references predate this compression — read them as *content*, not as this doc's calendar.
- `_docs/tech-stack-decision.md` — why each tech pick, not just what.
- `_docs/repo-structure.md` — folder layout; every task names the folder it lands in.
- `_docs/migrations/0001_core_schema.sql` + `_docs/migrations/0002_sheets_and_lot_grain.sql` — **locked** schema contract. Read-only for everyone except the backend/DB owner, and only changed via a new numbered migration + team agreement.
- `CLAUDE.md` (repo root) — read-order, git rules, delegation policy, and the progress-tracking convention these files use.

## People

| # | Role | One-line mandate |
|---|------|-------------------|
| 1 | **Coordinator — legal, data & stakeholder liaison** (owner/buyer + team member) | Gathers everything the builders need from outside the codebase: input files, API keys, Oksana's time and feedback, legal/compliance guardrails, journalist workflow examples, handover paperwork. |
| 2 | **Backend / DB developer** | Owns the Postgres schema, the DB access layer, the DAG/execution engine, and the API surface the frontend and recipes consume. |
| 3 & 4 | **Data Science / Agentic developers** (shared list — 2 people split it) | One leans document scans/extraction (docling, OCR, chunking, citations, structured extract), the other leans agentic recipes (Web Search, Match & Verify, Cross-row connect). Both write recipes against the shared contract in `recipes/base.py`. |
| 5 | **Frontend developer/designer** | Grid UX, citation/source view, recipe builder + Preview UI, SSE streaming, sort/filter, Result/export. |

## Weekly gates

Must hold before moving on (ARCHITECTURE.md §14). `Gate status` ∈ `PENDING` / `MET`, **edited only by the coordinator** — a week does not advance until its gate is `MET`:

| Wk | Target date | Gate | Gate status |
|---|---|---|---|
| 1 | 2026-07-28 | One real lot row completes the whole core loop (connector → recipe → column → Result), no manual data substitution. | `PENDING` |
| 2 | 2026-08-04 | Web Search produces a verifiable column on a representative subset, **and** Oksana builds a ≥2-column recipe sequence herself. | `PENDING` |
| 3 | 2026-08-11 | First Result is already useful in the pilot investigation. | `PENDING` |
| 4 | 2026-08-18 | Oksana does the core loop solo, critical recipes pass agreed eval thresholds, and an end-to-end real-case run stands on its own (Demo Day). | `PENDING` |
| buffer | 2026-08-19 – 2026-08-28 | No committed gate — reserved for slip + spare-capacity hardening (§14a). Not a second Demo Day. | `N/A` |

## How to read a task

Status → Target date → Description → Inputs (what must exist before you start) → Deliverable (what "done" looks like) → **Verify** (the command or check that proves it) → Depends on (who/what blocks you) → Reference (where to read the spec).

## Progress tracking

Each task carries a `Status` line — the single source of truth for that task. Tokens: `TODO` · `WIP` · `BLOCKED` · `REVIEW` · `DONE` (defined in `CLAUDE.md §3`). Update **only** the `Status` line of the task you own, optionally appending `@who branch/pr` or a blocker reason. `Target date` is a plan fact, not a live field — if a task's date is clearly wrong once work starts, raise it with the coordinator rather than silently editing it (same one-line discipline as `Status`). Never reflow the rest of a task file — see `CLAUDE.md §5` for why. Don't start a task whose `Depends on` isn't `DONE`; if it's blocked, set `BLOCKED` with the reason so the coordinator can clear it.

## Verify — what `DONE` has to survive

Every code task carries a **Verify** line: the command (or, for frontend and human-loop tasks, the one manual check) that demonstrates the deliverable. Rules:

- Don't set `REVIEW` until `Verify` passes. "It works on my machine" isn't the receipt; the command output is.
- If the test file a `Verify` line names doesn't exist yet, **writing it is part of the task** — that's the point, not an obstacle.
- A test that silently skips is not a pass. Backend DB tests skip without `CS_TEST_DATABASE_URL`; set it before claiming a DB-backed task verified.
- If a task's `Verify` turns out to be wrong or unprovable as written, fix the line in the same PR and say why. A `Verify` nobody can run is worse than none.
- Gate tasks additionally need the human check named in their line — a green suite doesn't prove a gate met.

---

## Buffer (2026-08-19 – 2026-08-28, ~1.5 weeks)

Deliberately **not** broken into per-role tasks — see ARCHITECTURE.md §14a. This window is what the 6→4 week compression recovered; it is held back, not deleted. Two uses, in priority order:

1. **Slip absorption.** If any Week 1–4 gate above is not `MET` on its target date, that gate's remaining tasks finish here before anything else starts. The coordinator tracks this the same way as any other blocker — `BLOCKED`/`WIP` status on the original task, not a new buffer-week task.
2. **Spare capacity.** Only once all four gates are `MET`: Custom Prompt recipe (if not already done in week 4), court/declaration sources, further hardening — in that order, per the original rev. 3 plan. Nothing from the Deferred list (§13) gets pulled forward into this window; see the Cross-role note below.

---

## Cross-role dependency notes

- **Everyone blocks on Role 2's `recipes/base.py`** (day 1) before writing real recipes — Role 2 should prioritize that class first, even ahead of the full DAG engine, so Role 3/4 aren't idle.
- **Role 2's migration `0002` (sheets + lot grain) lands week 1, not later** — Structured Extract, Expand, and Pair builder all assume `sheet`/`row_link`/`target_depth` exist from the start; retrofitting them mid-pilot would be far more expensive than landing both migrations together on day 1.
- **Role 3/4's citation anchoring blocks Role 5's source view** — coordinate the `citation_jsonb` array shape directly between these tracks early, don't wait for it to surface as a mismatch in week 2.
- **Role 1's key handoff blocks Role 2's YouControl connector**, which in turn blocks Role 3/4's Match & Verify and Role 5's registry-field display. Get the key handoff done in the first two days of week 1.
- **Role 1's eval rubric blocks Classify/Score (Role 3/4) and the feedback UI (Role 5)** — needed by week 2 now (was week 3), so start it week 1.
- **Role 2's Expand backend blocks Role 3/4's Expand recipe layer, which blocks Pair builder (both roles), which blocks Role 5's Pairs sheet display and Role 2's multi-sheet export** — this is the critical chain for the week 3 gate ("First Result is already useful"); don't let any one link slip without flagging it immediately.
- **Nothing in §13 (Deferred list)** — Merge, Recursive/Expand walk, Assistant Plan/Auto, fixed row-class taxonomy, Translation recipe/English UI, nested cases, multimedia, handwriting OCR, CMS/alerts — gets a task, in a build week **or** the buffer. If someone finishes early, more P0 hardening beats starting a Deferred item.
- **A dependency handed off is a dependency announced.** When your task is someone else's `Depends on`, tell them the moment it's `DONE` — and drop a handoff note in `_docs/handoffs/` if the next person (or the next agent session) needs context the task line doesn't carry.
