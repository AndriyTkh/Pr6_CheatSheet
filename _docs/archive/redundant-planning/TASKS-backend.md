# CheatSheet — Backend / DB Task Plan (Role 2) — ARCHIVED

> **⚠️ SUPERSEDED — do not edit, do not read for status. The live Role 2 list is `_docs/tasks/role-2.md`.**
>
> This was the first split (Role 2 only, while the other three roles were still inside `_docs/TASKS.md`). The rev. 3 workflow pass finished that split for every role, so this file became a second copy of the same tasks — exactly the two-trackers-out-of-sync problem `CLAUDE.md §3` forbids, and it did drift: the week-1 `Status` lines here were live while `role-2.md` still read `TODO`. Those seven statuses were ported to `_docs/tasks/role-2.md` before this file was archived; task text and target dates were byte-identical.
>
> Kept only as history. If you want to know what Role 2 is doing, open `_docs/tasks/role-2.md`.

**This file owned Role 2's task list only.** Split out of `_docs/TASKS.md` to keep that doc from growing unbounded and let Role 2 iterate on their own section without touching lines the other roles edit. Everything else — read order, doc map, progress-tracking convention, weekly gates, other roles' lists, cross-role dependency notes — lived in `_docs/TASKS.md`.

**Same rules applied here as in `TASKS.md`:** `CLAUDE.md §3` progress-tracking convention (`Status` token per task, edit only your own line), `CLAUDE.md §5` git rules (branch per task, never reflow this doc). `§N` references point to `_docs/ARCHITECTURE.md` unless marked `[owner-brief §N]`.

---

## Role 2 — Backend / DB developer

Mandate: the schema is already locked (`_docs/migrations/0001_core_schema.sql`, extended by `0002_sheets_and_lot_grain.sql`) — your job is to build everything on top of it without drifting from it: ORM models, the DAG/execution engine, the job queue wiring, and the API the frontend and recipes call. Folder: `backend/app/`. Primary references: §2, §2a, §4, §11, §15.

### Week 1 (2026-07-22 – 2026-07-28)

- **Task: Mirror the locked schema into SQLAlchemy models — including `0002`**
  - **Status:** `REVIEW` @andriy role-2/wk1-models-recipe-dag
  - **Target date:** `2026-07-22`
  - Description: Write async SQLAlchemy 2.0 models in `backend/app/models/` matching every table/enum in `0001_core_schema.sql` **and `0002_sheets_and_lot_grain.sql`** exactly — `sheet`, `row_link`, the `row.parent_row_id`/`depth`/`ordinal`/`position`/`tender_id`/`lot_id` columns, `column.target_depth`/`item_type`, `column_input.is_required`/`consumes`, and the `NotApplicable` enum value. Land both migrations together — the pilot builds on lot grain + sheets from day one, not as a week-4 retrofit. Do not add fields the migrations don't have; do not edit either migration to match convenient ORM shapes — they're the contract (§2, §2a).
  - Inputs: `_docs/migrations/0001_core_schema.sql`, `_docs/migrations/0002_sheets_and_lot_grain.sql`.
  - Deliverable: `models/` populated, DB session (`db/session.py`) connecting to a real Postgres 15+ instance with `pgcrypto`/`vector` extensions enabled, both migrations applied.
  - Depends on: nothing (migrations already exist).
  - Reference: §2, §2a.

- **Task: Stand up FastAPI app skeleton + core config**
  - **Status:** `REVIEW` @andriy role-2/wk1-models-recipe-dag — skeleton/config/health done; secret *values* still pending Role 1
  - **Target date:** `2026-07-23`
  - Description: `main.py` entrypoint, `core/config.py` for settings (DB URL, OpenRouter key, R2 credentials, YouControl key — all from env, never hardcoded), basic health-check route.
  - Inputs: dependency register (Role 1) for what env vars/secrets to wire in.
  - Deliverable: app boots, connects to DB.
  - Depends on: Role 1 handing off the YouControl key + other secrets.
  - Reference: §15.

- **Task: Recipe contract (`recipes/base.py`)**
  - **Status:** `REVIEW` @andriy role-2/wk1-models-recipe-dag — Role 3/4 can start writing recipes against it
  - **Target date:** `2026-07-22`
  - Description: Implement the actual `Recipe` class per §3 — `id/name/version`, `exec_type` (func/agent), `input` (each flagged `required`/`optional` **and** `whole_list`/`per_item`, §2a/§3), `params`/`output` schemas (JSON Schema, enforced server-side per §3's last bullet), `exec()`, `cite`, `eval`. This is the shared contract Role 3/4 build every recipe against — get it stable **before** they start writing recipes in parallel, so prioritize it on day one alongside the models task, not after.
  - Inputs: none.
  - Deliverable: `Recipe` base class + schema-validation enforcement (bad JSON from an LLM → `Error`/`NeedsReview`, never a silent malformed value).
  - Depends on: nothing, but blocks Role 3/4's recipe work — the single highest-priority task this week.
  - Reference: §3.

- **Task: Prozorro connector (row-producing, lot grain)**
  - **Status:** `REVIEW` @andriy role-2/wk1-models-recipe-dag — extraction + persistence tested against a recorded payload; one *live* tender still to pull
  - **Target date:** `2026-07-24`
  - Description: Implement `connectors/prozorro.py` per §6a — `GET /tenders` feed (cursor pagination, sync-by-`dateModified`), `GET /tenders/{id}`, documents list, deterministic winner extraction (`award.status='active'` **and** `award.lotID == lot.id` → `suppliers[].identifier.id`, filtered to `scheme='UA-EDR'` for EDRPOU; non-`UA-EDR` bidders → `NotApplicable`, not `NotFound`, §16 #9), `award.value`. **One row per tender lot** (§16 #3) — a tender with no `lots[]` still yields exactly one row, `lotID = null`. No LLM — this is pure structured extraction. Wire it as the row-producing recipe (`recipes/row_producing/`).
  - Inputs: none (public API, no auth).
  - Deliverable: one real tender pulled end-to-end into lot row(s), correct `provenance_jsonb` keyed by `(tenderID, lotID)`, landing on the source `@tenders` sheet.
  - Depends on: models/DB task above.
  - Reference: §6, §6a, §16 #3.

- **Task: YouControl connector (cell-producing) + server-side key proxy**
  - **Status:** `BLOCKED` waiting on Role 1 YouControl key + module/license confirmation
  - **Target date:** `2026-07-25`
  - Description: Implement `connectors/youcontrol.py` per §6a — registry (USR) lookup by EDRPOU at minimum; note which metered add-on modules the license actually covers (confirm with Role 1's week-1 spike) before wiring recipes that assume them. Key lives server-side only, one proxy endpoint, rate-limited, logged without the secret itself.
  - Inputs: YouControl key from Role 1; module/license confirmation.
  - Deliverable: registry fields fillable on a row given an EDRPOU.
  - Depends on: Role 1's key handoff + module verification.
  - Reference: §6a, §11.

- **Task: Minimal DAG engine — cycle check + list gate + topo sort**
  - **Status:** `REVIEW` @andriy role-2/wk1-models-recipe-dag — plus the §2 invariants 2–4 (`dag/invariants.py`), pulled forward from week 3
  - **Target date:** `2026-07-25`
  - Description: `dag/` — cycle detection on `column_input` edge-add (reject edges that close a loop), **the §2a expansion gate** at the same edge-add point (reject a `per_item` input pointed at a `value_type='list'` column, with a message naming the column and the two Expand modes), and topo-sort of the affected subgraph. Both checks are app-side validation on the add-column action — no cell created, nothing enqueued, nothing spent (§4 step 2).
  - Inputs: models task.
  - Deliverable: adding a column either succeeds or is rejected for cycles or for the list gate.
  - Depends on: models.
  - Reference: §4 steps 1–3, §2a.

- **Task: Get one recipe through Preview → run → column → Result (week 1 gate)**
  - **Status:** `WIP` @andriy role-2/wk1-models-recipe-dag — `services/row_ingest.py` runs the loop end to end; needs a live Postgres + a real tender to close
  - **Target date:** `2026-07-28`
  - Description: Wire whichever P0 recipe the team picked (kickoff decision, Role 1 — **Structured Extract** is ARCHITECTURE.md's flagged priority candidate, §6) through the full loop on one real lot row: add column → preview → confirm → background run (can be synchronous for week 1, Procrastinate wiring can follow week 2) → cell filled → visible as a Result.
  - Inputs: Prozorro connector, recipe contract, at least a stub grid (Role 5) or direct DB inspection.
  - Deliverable: the literal week 1 gate.
  - Depends on: everything above in this week.
  - Reference: §14 week 1 gate.

### Week 2 (2026-07-29 – 2026-08-04) — merges the original plan's weeks 2+3

- **Task: Wire Procrastinate as the real job queue**
  - **Status:** `TODO`
  - **Target date:** `2026-07-29`
  - Description: `tasks/` — Procrastinate app + cell-execution task, backed by Postgres `LISTEN/NOTIFY` + `SKIP LOCKED`. `cell.status` stays data/display only, never the lock target (§4's explicit warning against a hand-rolled poller fighting the real queue).
  - Inputs: DAG engine (week 1).
  - Deliverable: cell jobs actually run through Procrastinate, not inline.
  - Depends on: week 1 DAG work.
  - Reference: §4, §15.

- **Task: Wavefront-gated enqueue + `cache_key` (depth-aware)**
  - **Status:** `TODO`
  - **Target date:** `2026-07-30`
  - Description: Implement §4 step 5 (blocked → enqueue on `LISTEN/NOTIFY` when inputs go terminal, **scoped to rows at the column's `target_depth`** so an inline-expanded sheet's two grains never cross, §2a) and step 6 (`cache_key = hash(recipe_version + input_hashes + params + model_id + output_slot)`, force-refresh/cache-bust path for volatile recipes).
  - Inputs: Procrastinate wiring.
  - Deliverable: a cell never runs before its inputs are ready; identical inputs cache-hit; off-grain rows never get a cell.
  - Depends on: Procrastinate task.
  - Reference: §4 steps 5–6, §2a.

- **Task: SSE streaming with batched flush**
  - **Status:** `TODO`
  - **Target date:** `2026-07-31`
  - Description: `realtime/` — stream cell updates to the frontend, coalesced (every 150–250ms or N cells, not one message per cell) to avoid re-render storms at pilot scale (~10-15k cells/case).
  - Inputs: wavefront enqueue producing terminal cells.
  - Deliverable: SSE endpoint the frontend can subscribe to.
  - Depends on: wavefront task.
  - Reference: §4 step 7.

- **Task: Reconcile-on-reconnect endpoint**
  - **Status:** `TODO`
  - **Target date:** `2026-08-01`
  - Description: `GET /case/:id/cells?since=<version>` — monotonic `cell.version` lets a reconnecting client catch up before resuming the live stream.
  - Inputs: SSE task.
  - Deliverable: no cells silently lost across a disconnect.
  - Depends on: SSE task.
  - Reference: §4 step 7.

- **Task: Staleness walk on column edit**
  - **Status:** `TODO`
  - **Target date:** `2026-08-01`
  - Description: The recursive CTE in §4 — mark downstream columns `stale` when an upstream one changes. Never auto-rerun; surface "new version available" for user confirm. Confirm the walk correctly crosses a sheet boundary when the upstream column feeds an Expand/Pair-builder recipe (§2a — "the DAG spans sheets at the sheet boundary only").
  - Inputs: DAG engine.
  - Deliverable: editing a column correctly greys dependents (same sheet and downstream derived sheets) without silently recomputing them.
  - Depends on: DAG engine.
  - Reference: §4 "Staleness," §5, §2a.

- **Task: API routes for grid consumption — sheets included**
  - **Status:** `TODO`
  - **Target date:** `2026-08-02`
  - Description: `api/routes/` — cases, **sheets**, rows, columns, cells, recipes, runs, documents. A case now has ≥1 sheet (§2a) — routes must scope rows/columns/cells by `sheet_id`, not assume one grid per case. This is the interface Role 5 builds the frontend against — get the shape stable and share it (OpenAPI schema, per tech-stack-decision.md's FE-type-generation plan) early.
  - Inputs: models.
  - Deliverable: routes returning real data across sheets; OpenAPI spec exportable for frontend TS type generation.
  - Depends on: models; blocks Role 5's real (non-mocked) integration.
  - Reference: §15 tech-stack-decision.md "Shared FE/BE types", §2a.

- **Task: Column-dependency support for derived-column inputs**
  - **Status:** `TODO`
  - **Target date:** `2026-08-03`
  - Description: Recipes must accept already-derived columns as inputs (Summarize/Classify built on top of Web Search output, etc.) — confirm DAG/cache-key handle chained derivation correctly.
  - Inputs: DAG/cache work above.
  - Deliverable: a 2+ column recipe chain runs correctly.
  - Depends on: this week's DAG/cache work.
  - Reference: §4, §6.

- **Task: `cell_feedback` capture endpoint**
  - **Status:** `TODO`
  - **Target date:** `2026-08-04`
  - Description: API route for the verdict/relevance/error-type/correct-value feedback form (§12), backing Oksana's 2-column-sequence session this week.
  - Inputs: eval rubric (Role 1).
  - Deliverable: feedback persists to `cell_feedback`.
  - Depends on: Role 1's rubric.
  - Reference: §12.

### Week 3 (2026-08-05 – 2026-08-11)

- **Task: Verify migration `0002` against a populated dev DB**
  - **Status:** `TODO`
  - **Target date:** `2026-08-05`
  - Description: By now the DB holds real connector volume (weeks 1–2). Confirm `0002`'s backfill (one implicit source sheet per case, `row.sheet_id`/`column.sheet_id` NOT NULL, `row_lot_grain_uq`) ran clean against it, and that the four app-side invariants it deliberately doesn't encode (§2 "Four invariants") are actually enforced in code: cell's row/column agree on `sheet_id`; a cell exists only where `row.depth = column.target_depth`; `inline` children share their parent's sheet, `new_table` children get a new one.
  - Inputs: weeks 1–2 connector volume.
  - Deliverable: verified-clean migration state + the four invariants covered by tests.
  - Depends on: week 1 models/migration task, real data volume.
  - Reference: §2, §2a.

- **Task: Expand recipe backend (inline + new_table, `row_link`)**
  - **Status:** `TODO`
  - **Target date:** `2026-08-06`
  - Description: Backend support for the **Expand** row-producing recipe (§2a, §6) — `mode='inline'` (children inserted into the source sheet at `depth=1`, `parent_row_id` set, `ordinal` = source-array index, parent cells rendered-not-duplicated) and `mode='new_table'` (children become rows of a new derived `sheet`, optional `dedup_by` on an identity key). Both modes write `row_link` (`relation='expanded_from'`) alongside the tree edge, so downstream code has one path to walk (§16 #2).
  - Inputs: DAG engine + wavefront (depth-aware), sheet/row_link models.
  - Deliverable: expanding `@participants` produces correct child rows in either mode, deduped correctly in `new_table` mode, with full lineage.
  - Depends on: week 1–2 DAG/wavefront work, `0002` models.
  - Reference: §2a, §6, §16 #2.

- **Task: Pair builder recipe backend**
  - **Status:** `TODO`
  - **Target date:** `2026-08-07`
  - Description: Backend support for **Pair builder** (§6, §8) — deterministic Phase-1 candidate-gen (blocking on shared attributes, reused from Cross-row connect's blocking logic) materializes unique unordered company pairs per lot as rows on a derived **Pairs sheet**, `row_link` `relation='pair_member'` for both members (`parent_row_id` null — a pair has no single tree parent, §16 #10). A lot with <2 bidders emits `NotApplicable`, not a missing row.
  - Inputs: Expand backend (Companies sheet must exist first), candidate-gen blocking logic.
  - Deliverable: Pairs sheet populated from real lot data, `NotApplicable` correctly emitted for uncontested lots.
  - Depends on: Expand recipe backend.
  - Reference: §2a, §6, §8, §16 #10.

- **Task: Dead-end lock (fires on ANY required input)**
  - **Status:** `TODO`
  - **Target date:** `2026-08-08`
  - Description: §6's engine feature — a recipe whose **any** required input (`column_input.is_required`, `0002`) is terminal-empty (`InsufficientData`/`NotFound`/`SourceUnavailable`) is guaranteed `InsufficientData` and never dispatched; `NotApplicable` propagates as itself, not downgraded. Optional inputs missing never lock. Negative-cache on `cache_key` so identical inputs don't re-hit a paid provider.
  - Inputs: cache-key infra (week 2), `is_required`/enum work from `0002`.
  - Deliverable: cost-safety verified — a known-empty or structurally-void chain doesn't re-spend, and the propagated status matches its cause (§5).
  - Depends on: week 2 cache work.
  - Reference: §6, §5.

- **Task: Google Sheets export — all sheets**
  - **Status:** `TODO`
  - **Target date:** `2026-08-09`
  - Description: Export current grid view (rows/columns/filters) to Google Sheets on full volume, now covering the source `@tenders` sheet plus the derived Companies and Pairs sheets.
  - Inputs: stable API routes, Expand + Pair builder backends.
  - Deliverable: working multi-sheet export on the real dataset.
  - Depends on: API routes, Expand/Pair builder.
  - Reference: [owner-brief §4 P0, §11], §2a.

### Week 4 (2026-08-12 – 2026-08-18) — merges the original plan's weeks 5+6, ends on Demo Day

- **Task: Idempotency cache on external calls**
  - **Status:** `TODO`
  - **Target date:** `2026-08-12`
  - Description: §11's crash-retry protection — short-TTL idempotency cache keyed `(recipe_version, row_id, column_id, call_args_hash)` on the server-side provider proxy, so a Procrastinate retry after a crash doesn't double-charge YouControl/LLM quota.
  - Inputs: connector proxy (week 1).
  - Deliverable: verified no double-charge on a simulated crash-retry.
  - Depends on: connector work.
  - Reference: §11.

- **Task: `external_ok` gate enforcement**
  - **Status:** `TODO`
  - **Target date:** `2026-08-13`
  - Description: Every recipe dispatch checks `external_ok` on every source document in `row_context`; any un-attested document blocks the run with a clear message, never a silent send.
  - Inputs: legal guardrails (Role 1).
  - Deliverable: verified block on an unattested-upload test case.
  - Depends on: Role 1 guardrails doc; feeds Role 1's security audit.
  - Reference: §11.

- **Task: Cost cap + permissions/security hardening pass**
  - **Status:** `TODO`
  - **Target date:** `2026-08-13`
  - Description: Verify case privacy defaults, role checks (owner/editor/viewer), no secrets in logs, cost caps active before full runs.
  - Inputs: audit checklist (Role 1).
  - Deliverable: sign-off from Role 1's audit task.
  - Depends on: Role 1 audit task (mutual).
  - Reference: §11.

- **Task: Freeze version, support the final held-out run + live demo**
  - **Status:** `TODO`
  - **Target date:** `2026-08-18`
  - Description: Tag/freeze the build, support the final frozen-held-out run and the live Demo Day run technically. If Demo Day slips, this task and the freeze move into the buffer (§14a) rather than being rushed.
  - Inputs: everything else.
  - Deliverable: stable, demoed system; handover-ready repo/infra state for Role 1's handover doc.
  - Depends on: all prior weeks.
  - Reference: §14 week 4 gate.
