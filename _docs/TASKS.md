# CheatSheet — Project Task Plan

**Purpose:** split the pilot — **4-week build + 1.5-week buffer** (compressed from the original 6-week plan, tighter external deadline; ARCHITECTURE.md §14/§14a) — into role-owned task lists. One column per person/pair, ordered by week, each task self-contained (what to do, what you need first, what you hand off, where to read details, and now **when it's due**).

**rev. 2 of this doc (this pass):** re-synced to ARCHITECTURE.md rev. 3/4 — lot grain, sheets, the expansion gate, `NotApplicable`, migration `0002`, and the Expand/Pair builder/Formula-Compute/Start recipes are now tasked (they weren't in rev. 1, which predated ARCHITECTURE.md's rev. 3 pass). Schedule compressed 6→4 weeks + buffer; every task gets a **Target date**, computed forward from kickoff (2026-07-22).

**Source docs** (read before starting, and whenever a task references a `§`):
- `_docs/ARCHITECTURE.md` — **the** technical contract. All `§N` references below point here unless marked `[owner-brief §N]`. `§14`/`§14a` is the build-order + buffer this doc's weeks are dated against.
- `_docs/archive/drive/Briefs & Vision/cheatsheet-owner-brief.md` — product/PM brief (Ukrainian), acceptance criteria, canonical user scenario (§5), demo contract (§13). Its own "week N" references predate this compression — read them as *content*, not as this doc's calendar.
- `_docs/tech-stack-decision.md` — why each tech pick, not just what.
- `_docs/repo-structure.md` — folder layout; every task below names the folder it lands in.
- `_docs/migrations/0001_core_schema.sql` + `_docs/migrations/0002_sheets_and_lot_grain.sql` — **locked** schema contract. Read-only for everyone except the backend/DB owner, and only changed via a new numbered migration + team agreement.
- `CLAUDE.md` (repo root) — read-order, git rules, and the progress-tracking convention this doc uses.

**People:**

| # | Role | One-line mandate |
|---|------|-------------------|
| 1 | **Coordinator — legal, data & stakeholder liaison** (owner/buyer + team member) | Gathers everything the builders need from outside the codebase: input files, API keys, Oksana's time and feedback, legal/compliance guardrails, journalist workflow examples, handover paperwork. |
| 2 | **Backend / DB developer** | Owns the Postgres schema, the DB access layer, the DAG/execution engine, and the API surface the frontend and recipes consume. |
| 3 & 4 | **Data Science / Agentic developers** (shared column — 2 people split the list) | One leans document scans/extraction (docling, OCR, chunking, citations, structured extract), the other leans agentic recipes (Web Search, Match & Verify, Cross-row connect). Both write recipes against the shared contract in `recipes/base.py`. |
| 5 | **Frontend developer/designer** | Grid UX, citation/source view, recipe builder + Preview UI, SSE streaming, sort/filter, Result/export. |

**Weekly gates** (must hold before moving on — ARCHITECTURE.md §14). `Gate status` ∈ `PENDING` / `MET`, **edited only by the coordinator** — a week does not advance until its gate is `MET`:

| Wk | Target date | Gate | Gate status |
|---|---|---|---|
| 1 | 2026-07-28 | One real lot row completes the whole core loop (connector → recipe → column → Result), no manual data substitution. | `PENDING` |
| 2 | 2026-08-04 | Web Search produces a verifiable column on a representative subset, **and** Oksana builds a ≥2-column recipe sequence herself. | `PENDING` |
| 3 | 2026-08-11 | First Result is already useful in the pilot investigation. | `PENDING` |
| 4 | 2026-08-18 | Oksana does the core loop solo, critical recipes pass agreed eval thresholds, and an end-to-end real-case run stands on its own (Demo Day). | `PENDING` |
| buffer | 2026-08-19 – 2026-08-28 | No committed gate — reserved for slip + spare-capacity hardening (§14a). Not a second Demo Day. | `N/A` |

**How to read a task:** Status → Target date → Description → Inputs (what must exist before you start) → Deliverable (what "done" looks like) → Depends on (who/what blocks you) → Reference (where to read the spec).

**Progress tracking (how this doc is used live):** each task carries a `Status` line — the single source of truth for that task. Tokens: `TODO` · `WIP` · `BLOCKED` · `REVIEW` · `DONE` (defined in `CLAUDE.md §3`). Update **only** the `Status` line of the task you own, optionally appending `@who branch/pr` or a blocker reason. `Target date` is a plan fact set by this rewrite, not a live field — if a task's date is clearly wrong once work starts, raise it with the coordinator rather than silently editing it (same one-line discipline as `Status`). Never reflow the rest of the doc — see `CLAUDE.md §5` for why. Don't start a task whose `Depends on` isn't `DONE`; if it's blocked, set `BLOCKED` with the reason so the coordinator can clear it.

---

## Role 1 — Coordinator: legal, data & stakeholder liaison

Mandate: you don't write product code. You keep the other four unblocked — real files, real access, real feedback, and you're the one who checks nothing in the pipeline breaks the "public data only" rule or leaves a secret somewhere it shouldn't be. Primary references: owner-brief §10–§12, §15; ARCHITECTURE.md §11.

### Week 1 (2026-07-22 – 2026-07-28)

- **Task: Run kickoff decisions to closure**
  - **Status:** `WIP` @marina
  - **Target date:** `2026-07-22`
  - Description: Drive the 7 decisions owner-brief §12 requires before the team splits up: who owns which stream, when Oksana picks company X and is available for the first workflow session, what the row v0 unit is (ARCHITECTURE.md now **locks** it — "one Prozorro tender *lot*", §16 #3, rev. 3's change from the earlier tender-package grain — get it confirmed against real data, not just accepted on paper), which P0 recipe ships first (ARCHITECTURE.md §6 now flags **Structured Extract** as the pilot-priority candidate — confirm or override), where the backlog lives and who makes product calls, what access/keys/quotas already exist vs. are missing, and what one-lot-row end-to-end result the team commits to showing at the end of week 1.
  - Inputs: owner-brief §12, the team itself.
  - Deliverable: a short written decision log (backlog location is fine) covering all 7 points.
  - Depends on: nothing — this is the first task of the project.
  - Reference: [owner-brief §12]; §16 #3, §6.

- **Task: Build the access/dependency register**
  - **Status:** `WIP` @marina
  - **Target date:** `2026-07-23`
  - Description: One document listing every external dependency the pilot touches: Prozorro API (public, no auth), YouControl API key + which licensed modules it actually covers (registry vs. metered add-ons — "having a key ≠ having all modules," §6a), OpenRouter key, Cloudflare R2 bucket/credentials, Railway project access, Google account(s) for Sheets/Docs export. For each: who holds it, where it's stored (never in the repo or client), what's still missing.
  - Inputs: whatever keys the team already has (owner-brief §10 notes YouControl's key already exists).
  - Deliverable: `dependency register` doc, kept current through the build weeks and the buffer.
  - Depends on: nothing to start; backend dev needs this register's contents (specifically the YouControl key) within the first two days.
  - Reference: §6a, §11; [owner-brief §10, §12.6, §15 "API й ключі"].

- **Task: Hand off secrets server-side only**
  - **Status:** `DONE` @marina
  - **Target date:** `2026-07-24`
  - Description: Get the YouControl key (and any other provider keys) to the backend developer through a private channel, never committed or pasted into shared docs/chat history that persists in the repo. Confirm with backend dev that the key lands behind one server-side proxy endpoint, not in frontend code or logs.
  - Inputs: keys from the dependency register.
  - Deliverable: confirmation the backend dev has what they need and it's not in git.
  - Depends on: dependency register task above; backend dev's connector work (Role 2, same week).
  - Reference: §11 "Secrets server-side only."

- **Task: Draft legal/compliance guardrails**
  - **Status:** `WIP` @marina
  - **Target date:** `2026-07-23`
  - Description: Write the operating rules for what counts as "public data" for this pilot, what "external_ok" attestation means in practice for a manually-uploaded file (§11), and what Ukrainian personal-data-handling considerations apply to company officer/beneficiary data pulled from YouControl (names, addresses, EDRPOU) even though the source registry itself is public. This is the checklist backend/DS devs test against, not a legal memo nobody reads.
  - Inputs: ARCHITECTURE.md §11 (external_ok gate), owner-brief §10 ("Дані").
  - Deliverable: a short guardrails doc + a plain-language checklist for "can this document/field go to an external LLM/API provider?"
  - Depends on: nothing.
  - Reference: §11; [owner-brief §10].

- **Task: Run Oksana's first workflow session**
  - **Status:** `DONE` @marina — notes: [Excalidraw workflow](https://link.excalidraw.com/l/5iKoSi2GiB4/91hpw3JuCS)
  - **Target date:** `2026-07-25`
  - Description: Schedule and sit in on Oksana walking through her *manual* process for the company-X case — this defines what a "logical row" needs to contain, what fields matter, and what failure states actually happen in practice (not just the ones in the doc). Capture it in writing/recording.
  - Inputs: Oksana's availability, company X chosen (may happen in this same session).
  - Deliverable: session notes handed to backend dev + DS/agentic pair — feeds row v0 confirmation and the first eval rubric.
  - Depends on: kickoff decisions task (company X pick).
  - Reference: [owner-brief §11, §5 canonical scenario].

- **Task: Draft the first eval rubric with Oksana**
  - **Status:** `TODO`
  - **Target date:** `2026-07-27`
  - Description: Get Oksana's verdict categories (correct/partial/incorrect/cannot judge), relevance scale (0–3), and error-type taxonomy turned into a written rubric the eval track can wire up from day one.
  - Inputs: owner-brief §8/§12 feedback-form spec.
  - Deliverable: rubric doc, shared with DS/agentic pair (they wire `cell_feedback` capture to it).
  - Depends on: Oksana's first session.
  - Reference: §12; [owner-brief §8].

### Week 2 (2026-07-29 – 2026-08-04) — merges the original plan's weeks 2+3

- **Task: Curate real input files for extraction/OCR testing**
  - **Status:** `TODO`
  - **Target date:** `2026-07-29`
  - Description: Collect a batch of real tender documents (scanned PDFs included) that are legitimately public, covering the messy cases (no text layer, mixed language) the DS/document track needs to test docling/OCR against. Validate each file's public-source status against the Week 1 guardrails before handing it over.
  - Inputs: guardrails checklist; Prozorro document links.
  - Deliverable: a vetted sample file set + a short note on source/provenance for each.
  - Depends on: legal guardrails task; Prozorro connector live (Role 2/3-4) to pull real doc links.
  - Reference: §7, §11; [owner-brief §4 P0 "базовий OCR"].

- **Task: Run Oksana's vertical-slice review**
  - **Status:** `TODO`
  - **Target date:** `2026-07-31`
  - Description: After this week's connector volume ramp-up, get Oksana to look at real rows and give first-pass feedback (not formal eval yet — sanity check).
  - Inputs: rows in the grid (Role 2/5 output).
  - Deliverable: feedback notes routed to whichever track they concern.
  - Depends on: Week 2 gate progress (Web Search producing a verifiable column).
  - Reference: [owner-brief §11].

- **Task: Curate dev/held-out examples per recipe**
  - **Status:** `TODO`
  - **Target date:** `2026-08-01`
  - Description: Work with Oksana to pick which real examples go into the tuning set vs. the frozen held-out set for each P0 recipe (Summarize, Classify/Score added this week). Held-out means held-out — no peeking to tune after it's frozen.
  - Inputs: recipe outputs so far; eval rubric.
  - Deliverable: labeled dev/held-out split, one per recipe, documented so nobody accidentally tunes on held-out.
  - Depends on: eval rubric (week 1); recipes live (Role 3-4).
  - Reference: §12; [owner-brief §8, §11].

- **Task: Keep the dependency register current**
  - **Status:** `TODO`
  - **Target date:** `2026-08-01`
  - Description: Add any new keys/quotas requested this week (embedding model, additional OpenRouter models, R2 bucket details).
  - Inputs: requests from backend/DS devs.
  - Deliverable: updated register.
  - Depends on: ongoing.
  - Reference: §11.

- **Task: Run Oksana's 2-column-sequence session (week 2 gate)**
  - **Status:** `TODO`
  - **Target date:** `2026-08-04`
  - Description: Sit Oksana down to build a ≥2-column recipe sequence herself — this *is* half of the week 2 gate (the other half is Web Search stabilizing), not just feedback. Capture friction points for frontend/recipe tracks.
  - Inputs: recipe builder UI (Role 5), ≥2 working recipes (Role 3-4).
  - Deliverable: gate confirmation + friction-point notes.
  - Depends on: frontend recipe builder, DS/agentic recipes reaching "usable" state.
  - Reference: [owner-brief §11]; §14 week 2 gate.

### Week 3 (2026-08-05 – 2026-08-11)

- **Task: Curate journalist workflow / pattern examples**
  - **Status:** `TODO`
  - **Target date:** `2026-08-05`
  - Description: Turn owner-brief §3's pattern list (repeated participant groups, price anomalies, timing red flags, shared addresses/directors, etc.) into concrete annotated examples from the real dataset — this is what the DS/agentic pair tunes Classify/Score and Cross-row connect/Pair builder against, and what Oksana's feedback pass (below) references.
  - Inputs: real row data (by now there should be hundreds); Oksana's domain knowledge.
  - Deliverable: annotated pattern-example doc.
  - Depends on: connector volume ramp-up (Role 2/3-4).
  - Reference: [owner-brief §3 "Що система може показати"].

- **Task: Coordinate Oksana's tuning feedback pass**
  - **Status:** `TODO`
  - **Target date:** `2026-08-08`
  - Description: Get Oksana's marks on the cross-row signals, the new Companies/Pairs sheets, and classification outputs so the DS/agentic pair can tune recipes this week.
  - Inputs: cross-row connect output, Pair builder output, Classify/Score output.
  - Deliverable: feedback logged in `cell_feedback` via the UI (Role 5) or relayed directly to Role 3-4.
  - Depends on: cross-row connect + Pair builder + classify/score working.
  - Reference: [owner-brief §11].

### Week 4 (2026-08-12 – 2026-08-18) — merges the original plan's weeks 5+6, ends on Demo Day

- **Task: Freeze the held-out set**
  - **Status:** `TODO`
  - **Target date:** `2026-08-12`
  - Description: Lock the held-out examples with Oksana — no further tuning against them from this point. Confirm the dev track has actually stopped touching them.
  - Inputs: held-out set from week 3 curation.
  - Deliverable: written confirmation of freeze date + scope.
  - Depends on: dev/held-out task (week 2).
  - Reference: §12; [owner-brief §8, §11].

- **Task: Legal/security audit pass**
  - **Status:** `TODO`
  - **Target date:** `2026-08-13`
  - Description: Verify (with backend dev) that no non-public material entered the pipeline, `external_ok` attestations are actually being checked and logged, and no secrets leaked into logs, the repo, or client-side code.
  - Inputs: guardrails checklist (week 1); backend dev's logging/proxy implementation.
  - Deliverable: audit sign-off or a punch list of fixes before Demo Day.
  - Depends on: backend security work (Role 2, §11 tasks).
  - Reference: §11; [owner-brief §11 "перевірка permissions, секретів"].

- **Task: Draft handover/IP documentation**
  - **Status:** `TODO`
  - **Target date:** `2026-08-13`
  - Description: Per owner-brief §15's "handover doesn't happen" risk — write down what transfers to Бабель: repo ownership, secrets/keys, hosting account, billing, domain, and who's the accepting owner on their side. Draft now, finalize once Demo Day results are in.
  - Inputs: dependency register; Railway/hosting account details from backend dev.
  - Deliverable: handover doc draft.
  - Depends on: dependency register being current.
  - Reference: [owner-brief §15 "Не відбудеться передача продукту"].

- **Task: Prep and coordinate the live demo run**
  - **Status:** `TODO`
  - **Target date:** `2026-08-17`
  - Description: Line up Oksana for the live run, prep a backup dataset/run in case of an external failure (API downtime, etc.) per the Demo Day gate.
  - Inputs: frozen held-out set; stable build (Role 2/5).
  - Deliverable: demo runbook + backup dataset ready.
  - Depends on: everything else landing this week.
  - Reference: §14 week 4 gate; [owner-brief §13 demo contract].

- **Task: Finalize handover + "what's next" decision doc**
  - **Status:** `TODO`
  - **Target date:** `2026-08-18`
  - Description: Close out the handover doc, and write up the Stop/Iterate/Operationalize/Expand recommendation per owner-brief §16. If Demo Day slips into the buffer (§14a), this task slips with it.
  - Inputs: handover draft; demo results.
  - Deliverable: final handover package + decision memo.
  - Depends on: Demo Day run.
  - Reference: [owner-brief §16].

---

## Role 2 — Backend / DB developer

Mandate: the schema is already locked (`_docs/migrations/0001_core_schema.sql`, extended by `0002_sheets_and_lot_grain.sql`) — your job is to build everything on top of it without drifting from it: ORM models, the DAG/execution engine, the job queue wiring, and the API the frontend and recipes call. Folder: `backend/app/`. Primary references: §2, §2a, §4, §11, §15.

### Week 1 (2026-07-22 – 2026-07-28)

- **Task: Mirror the locked schema into SQLAlchemy models — including `0002`**
  - **Status:** `TODO`
  - **Target date:** `2026-07-22`
  - Description: Write async SQLAlchemy 2.0 models in `backend/app/models/` matching every table/enum in `0001_core_schema.sql` **and `0002_sheets_and_lot_grain.sql`** exactly — `sheet`, `row_link`, the `row.parent_row_id`/`depth`/`ordinal`/`position`/`tender_id`/`lot_id` columns, `column.target_depth`/`item_type`, `column_input.is_required`/`consumes`, and the `NotApplicable` enum value. Land both migrations together — the pilot builds on lot grain + sheets from day one, not as a week-4 retrofit. Do not add fields the migrations don't have; do not edit either migration to match convenient ORM shapes — they're the contract (§2, §2a).
  - Inputs: `_docs/migrations/0001_core_schema.sql`, `_docs/migrations/0002_sheets_and_lot_grain.sql`.
  - Deliverable: `models/` populated, DB session (`db/session.py`) connecting to a real Postgres 15+ instance with `pgcrypto`/`vector` extensions enabled, both migrations applied.
  - Depends on: nothing (migrations already exist).
  - Reference: §2, §2a.

- **Task: Stand up FastAPI app skeleton + core config**
  - **Status:** `TODO`
  - **Target date:** `2026-07-23`
  - Description: `main.py` entrypoint, `core/config.py` for settings (DB URL, OpenRouter key, R2 credentials, YouControl key — all from env, never hardcoded), basic health-check route.
  - Inputs: dependency register (Role 1) for what env vars/secrets to wire in.
  - Deliverable: app boots, connects to DB.
  - Depends on: Role 1 handing off the YouControl key + other secrets.
  - Reference: §15.

- **Task: Recipe contract (`recipes/base.py`)**
  - **Status:** `TODO`
  - **Target date:** `2026-07-22`
  - Description: Implement the actual `Recipe` class per §3 — `id/name/version`, `exec_type` (func/agent), `input` (each flagged `required`/`optional` **and** `whole_list`/`per_item`, §2a/§3), `params`/`output` schemas (JSON Schema, enforced server-side per §3's last bullet), `exec()`, `cite`, `eval`. This is the shared contract Role 3/4 build every recipe against — get it stable **before** they start writing recipes in parallel, so prioritize it on day one alongside the models task, not after.
  - Inputs: none.
  - Deliverable: `Recipe` base class + schema-validation enforcement (bad JSON from an LLM → `Error`/`NeedsReview`, never a silent malformed value).
  - Depends on: nothing, but blocks Role 3/4's recipe work — the single highest-priority task this week.
  - Reference: §3.

- **Task: Prozorro connector (row-producing, lot grain)**
  - **Status:** `TODO`
  - **Target date:** `2026-07-24`
  - Description: Implement `connectors/prozorro.py` per §6a — `GET /tenders` feed (cursor pagination, sync-by-`dateModified`), `GET /tenders/{id}`, documents list, deterministic winner extraction (`award.status='active'` **and** `award.lotID == lot.id` → `suppliers[].identifier.id`, filtered to `scheme='UA-EDR'` for EDRPOU; non-`UA-EDR` bidders → `NotApplicable`, not `NotFound`, §16 #9), `award.value`. **One row per tender lot** (§16 #3) — a tender with no `lots[]` still yields exactly one row, `lotID = null`. No LLM — this is pure structured extraction. Wire it as the row-producing recipe (`recipes/row_producing/`).
  - Inputs: none (public API, no auth).
  - Deliverable: one real tender pulled end-to-end into lot row(s), correct `provenance_jsonb` keyed by `(tenderID, lotID)`, landing on the source `@tenders` sheet.
  - Depends on: models/DB task above.
  - Reference: §6, §6a, §16 #3.

- **Task: YouControl connector (cell-producing) + server-side key proxy**
  - **Status:** `TODO`
  - **Target date:** `2026-07-25`
  - Description: Implement `connectors/youcontrol.py` per §6a — registry (USR) lookup by EDRPOU at minimum; note which metered add-on modules the license actually covers (confirm with Role 1's week-1 spike) before wiring recipes that assume them. Key lives server-side only, one proxy endpoint, rate-limited, logged without the secret itself.
  - Inputs: YouControl key from Role 1; module/license confirmation.
  - Deliverable: registry fields fillable on a row given an EDRPOU.
  - Depends on: Role 1's key handoff + module verification.
  - Reference: §6a, §11.

- **Task: Minimal DAG engine — cycle check + list gate + topo sort**
  - **Status:** `TODO`
  - **Target date:** `2026-07-25`
  - Description: `dag/` — cycle detection on `column_input` edge-add (reject edges that close a loop), **the §2a expansion gate** at the same edge-add point (reject a `per_item` input pointed at a `value_type='list'` column, with a message naming the column and the two Expand modes), and topo-sort of the affected subgraph. Both checks are app-side validation on the add-column action — no cell created, nothing enqueued, nothing spent (§4 step 2).
  - Inputs: models task.
  - Deliverable: adding a column either succeeds or is rejected for cycles or for the list gate.
  - Depends on: models.
  - Reference: §4 steps 1–3, §2a.

- **Task: Get one recipe through Preview → run → column → Result (week 1 gate)**
  - **Status:** `TODO`
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

---

## Role 3 & 4 — Data Science / Agentic developers (shared column)

Two people, one list — split by whichever half fits each person better, but keep both halves moving in parallel since they share the recipe contract (`recipes/base.py`, owned by Role 2) and the same eval loop (§12). **Track A: document scans/extraction.** **Track B: agentic recipes.** Folder: `backend/app/documents/`, `backend/app/citations/`, `backend/app/agents/`, `backend/app/recipes/`. Each task is tagged `[Track A]` / `[Track B]` / `[either track]` so the two of you edit different `Status` lines — never the same one.

### Week 1 (2026-07-22 – 2026-07-28)

- **Task [either track]: Recipe catalog stubs against the contract**
  - **Status:** `TODO`
  - **Target date:** `2026-07-23`
  - Description: Once Role 2 ships `recipes/base.py`, stub out the P0 recipe classes (§6 table — including **Expand**, **Pair builder**, **Formula/Compute**, **Start** which weren't previously tasked here) in `recipes/cell_producing/`, `recipes/row_producing/`, `recipes/cross_row/` so both people can build in parallel without stepping on each other. Pick and fully implement the recipe the team chose in the kickoff decision (Role 1 task) first — that's the week 1 gate.
  - Inputs: `recipes/base.py` (Role 2).
  - Deliverable: stubs exist; the chosen first recipe works end to end.
  - Depends on: Role 2's recipe contract.
  - Reference: §3, §6.

- **Task [Track A — docs]: docling ingest pipeline**
  - **Status:** `TODO`
  - **Target date:** `2026-07-24`
  - Description: `documents/` — wire docling for PDF/DOCX/XLSX/PPTX/HTML parsing, text-layer check before OCR, Tesseract backend (ukr+rus+eng traineddata) only on pages that actually lack a text layer. No raw pytesseract calls outside docling.
  - Inputs: sample files (Role 1, curated batch arrives week 2, but Prozorro connector docs can be a first source in week 1).
  - Deliverable: a manually-uploaded or Prozorro-sourced doc parses into normalized content + per-element page/bbox.
  - Depends on: Role 2's Prozorro connector for doc links, or Role 1's manual samples.
  - Reference: §7, §9, §15.

- **Task [Track A — priority]: Structured Extract — lazy/hybrid, full spec**
  - **Status:** `TODO`
  - **Target date:** `2026-07-25`
  - Description: ARCHITECTURE.md rev. 3 promotes this to the pilot-priority recipe (§6, §16 #4) — its interface must be stable before the rest of parallel recipe work leans on it, so build it early, not in week 3 as the original plan had it. Deterministic extraction from already-structured connector data (no LLM); LLM only for unstructured fragments, on-demand per §7's "hybrid, lazy default." One question = one output column, always 1:1; several answers for a row land as one typed **list** cell with per-item citations, never as extra rows (§2a); absence → `NotFound` + zero citations, never a guess.
  - Inputs: docling pipeline; connector data; recipe contract.
  - Deliverable: working recipe, both the deterministic and LLM-lazy paths, list-output case included — likely candidate to satisfy the week 1 gate.
  - Depends on: docling + connectors + recipe contract.
  - Reference: §6 "Structured Extract — full spec", §7, §2a.

- **Task [Track B — agentic]: Web Search recipe skeleton**
  - **Status:** `TODO`
  - **Target date:** `2026-07-24`
  - Description: Tool-using loop, row-scoped: build query from selected columns, call search tool, select relevant results, explain the choice. Output schema per §3 (JSON-schema enforced).
  - Inputs: recipe contract; OpenRouter access (dependency register, Role 1).
  - Deliverable: a stub that runs and returns a typed, cited result on one row.
  - Depends on: Role 2's recipe contract + OpenRouter key.
  - Reference: §6, §8.

- **Task [Track B]: Start router recipe**
  - **Status:** `TODO`
  - **Target date:** `2026-07-26`
  - Description: Row-producing recipe (§6) — journalist's question + new column name → func+LLM router proposes a connector (Prozorro / web search / …) or asks for an upload. **The journalist approves before any run** (§4 step 4 Preview gate) — the router proposes, it never auto-executes. Not on the critical path for the demo (Prozorro is hardcoded for the pilot case), but it's a P0 recipe in the catalog and cheap to land now alongside the other row-producing work.
  - Inputs: recipe contract.
  - Deliverable: router proposes a connector/upload path for a sample question, gated behind Preview confirm.
  - Depends on: Role 2's recipe contract.
  - Reference: §6 "Start".

### Week 2 (2026-07-29 – 2026-08-04) — merges the original plan's weeks 2+3

- **Task [Track A]: Chunking + embeddings**
  - **Status:** `TODO`
  - **Target date:** `2026-07-29`
  - Description: Chunk parsed documents, embed with a pinned embedding model (`embed_model_id` recorded per chunk, §10 — never a floating model), store in `pgvector`.
  - Inputs: docling pipeline.
  - Deliverable: chunks + embeddings queryable.
  - Depends on: docling task.
  - Reference: §7, §10.

- **Task [Track A]: Citation quote→locate anchoring**
  - **Status:** `TODO`
  - **Target date:** `2026-07-30`
  - Description: `citations/` — model/extraction returns a verbatim quote, code string-searches it back into the source for the offset. Never trust a model-reported page number. Add fuzzy locate (normalize + token-window/edit-distance) for OCR'd text, with `match_confidence`; below threshold → `NeedsReview`, don't store a guessed offset. `citation_jsonb` is an array aligned to `value_jsonb` — cover the list-cell case (Structured Extract's list output) now, not as a later patch.
  - Inputs: chunking task; docling per-element page/bbox.
  - Deliverable: citations resolve to a real, verifiable location for both clean-text and OCR'd docs, including per-item citations on list cells.
  - Depends on: chunking + docling tasks.
  - Reference: §9, §2a.

- **Task [Track B]: Match & Verify recipe**
  - **Status:** `TODO`
  - **Target date:** `2026-07-31`
  - Description: Agent loop, row-scoped, fixed tool = YouControl: choose search strategy (EDRPOU → name → person) → call → compare to row data → typed status + explanation + sources. Declares `per_item` consumption (§6 table) — blocked on a list input until Expand runs.
  - Inputs: YouControl connector (Role 2).
  - Deliverable: working recipe on real rows.
  - Depends on: Role 2's YouControl connector.
  - Reference: §6, §8.

- **Task [Track B]: Stabilize Web Search into a verifiable column (week 2 gate, half)**
  - **Status:** `TODO`
  - **Target date:** `2026-08-01`
  - Description: This is half the week 2 gate — Web Search must produce a column Oksana/Role 1 can actually verify against citations on a representative subset of rows.
  - Inputs: Web Search skeleton (week 1); citation anchoring (Track A, ideally landed by now — coordinate).
  - Deliverable: gate met.
  - Depends on: Track A's citation work landing in parallel.
  - Reference: §14 week 2 gate.

- **Task [either track]: Summarize recipe**
  - **Status:** `TODO`
  - **Target date:** `2026-08-02`
  - Description: LLM recipe, text column → short column, citation-entailment checked at eval time. Must accept a derived column as input (e.g. Web Search output) — confirm with Role 2's column-dependency work. Declares `whole_list` (§6 table) — a list input is read as context, not exploded.
  - Inputs: recipe contract; citation anchoring.
  - Deliverable: working recipe.
  - Depends on: Role 2's derived-column-input support.
  - Reference: §6.

- **Task [either track]: Classify/Score recipe**
  - **Status:** `TODO`
  - **Target date:** `2026-08-03`
  - Description: LLM recipe against a transparent, editable rubric preset (Oksana-defined, per Role 1's rubric task, recorded in `column.params_jsonb` per §3 "presets"), typed label/score output.
  - Inputs: eval rubric (Role 1).
  - Deliverable: working recipe.
  - Depends on: Role 1's rubric.
  - Reference: §6, §3.

- **Task [either track]: dev/held-out wiring per recipe**
  - **Status:** `TODO`
  - **Target date:** `2026-08-04`
  - Description: Make sure each recipe's eval path can run against the dev/held-out split Role 1 is curating this week.
  - Inputs: Role 1's split.
  - Deliverable: eval runnable per recipe.
  - Depends on: Role 1.
  - Reference: §12.

### Week 3 (2026-08-05 – 2026-08-11)

- **Task [either track]: Deterministic comparisons (Aggregate/Fold, Compare/Diff, Formula/Compute)**
  - **Status:** `TODO`
  - **Target date:** `2026-08-05`
  - Description: Code-based (not LLM) recipes finding repeated companies/attributes/patterns — exact counts and matches are code, per §3's "not everything is an LLM" rule. Includes **Formula/Compute** (arithmetic/date-diff/ratio over referenced columns — e.g. days between company registration and tender date; `length()`/`contains()`/index access on lists, arithmetic requires a *typed* list, untyped rejected at edge-add, §6 table), previously untasked here.
  - Inputs: real volume of rows.
  - Deliverable: working recipes surfacing repeated participants/attributes and computed columns.
  - Depends on: connector volume (Role 2).
  - Reference: §3, §6.

- **Task [Track A or either]: Expand recipe (application layer)**
  - **Status:** `TODO`
  - **Target date:** `2026-08-06`
  - Description: The recipe-side half of Expand (§2a, §6) — pairs with Role 2's backend task. Wire `mode` param (`inline`/`new_table`), `dedup_by`, and confirm output onto `recipes/row_producing/`. This is what unblocks `@participants` → Companies sheet for the Act 2 workflow.
  - Inputs: Role 2's Expand backend, recipe contract.
  - Deliverable: expanding `@participants` from a real tender produces Companies-sheet rows with correct dedup.
  - Depends on: Role 2's Expand backend.
  - Reference: §2a, §6.

- **Task [Track B or either]: Pair builder recipe (application layer)**
  - **Status:** `TODO`
  - **Target date:** `2026-08-07`
  - Description: Recipe-side half of Pair builder (§2a, §6, §8) — pairs with Role 2's backend task. Aggregates co-bid count, win split, shared owner/address per pair; emits `NotApplicable` for lots with <2 bidders. Reuses the same deterministic blocking logic as Cross-row connect's Phase 1.
  - Inputs: Role 2's Pair builder backend, Expand recipe (Companies sheet must exist).
  - Deliverable: Pairs sheet populated with real co-bid/win-split/shared-attribute signals.
  - Depends on: Expand recipe, Role 2's Pair builder backend.
  - Reference: §2a, §6, §8.

- **Task [Track B]: Cross-row connect — narrowed scope**
  - **Status:** `TODO`
  - **Target date:** `2026-08-08`
  - Description: Two-phase — deterministic candidate-gen (block on shared phone/email/address/EDRPOU/director/owner to cut N² to a handful, shared code with Pair builder's Phase 1), then agentic verify per candidate pair (compare, explore YouControl/web, typed status + evidence citing the shared attribute *and* both source records). Rev. 3 **narrows** this recipe's scope: anything with a stable pair grain (repeated co-bidding, win split, shared owner/address) now belongs on the Pairs sheet instead — Cross-row connect stays for genuinely one-off, no-row-shape signals only. Writes to `cross_row_result`, not a grid cell.
  - Inputs: candidate attributes available on rows (connector data); Pair builder landing in parallel (defines what's now out of scope here).
  - Deliverable: signal generation on real row pairs limited to no-row-shape cases, with evidence.
  - Depends on: sufficient row volume + registry data; Pair builder recipe (to know what NOT to duplicate here).
  - Reference: §8, §16 #10.

- **Task [either track]: Tune recipes on Oksana's marks**
  - **Status:** `TODO`
  - **Target date:** `2026-08-09`
  - Description: Use Role 1's curated pattern examples + Oksana's feedback pass to adjust prompts/rubrics on Classify/Score, Pair builder, and Cross-row connect.
  - Inputs: Role 1's pattern-example doc + feedback.
  - Deliverable: measurably improved eval numbers on the dev set.
  - Depends on: Role 1's week 3 tasks.
  - Reference: §12.

### Week 4 (2026-08-12 – 2026-08-18) — merges the original plan's weeks 5+6, ends on Demo Day

- **Task [either track]: Run against dev/validation only, fix errors found**
  - **Status:** `TODO`
  - **Target date:** `2026-08-12`
  - Description: Fix citation mismatches, source errors, stale-dependency bugs surfaced by hardening runs. Do not touch the frozen held-out set.
  - Inputs: frozen held-out boundary (Role 1).
  - Deliverable: error list closed out or triaged.
  - Depends on: Role 1's freeze.
  - Reference: [owner-brief §11].

- **Task [Stretch, if capacity allows]: Custom Prompt recipe**
  - **Status:** `TODO`
  - **Target date:** `2026-08-14`
  - Description: Only after the above is solid — free-form prompt as its own recipe, per-use rubric. If capacity runs out this week, this is exactly the kind of item that moves into the buffer (§14a) rather than being rushed.
  - Inputs: spare capacity.
  - Deliverable: working Stretch recipe.
  - Depends on: everything else this week being done first.
  - Reference: §6 "Custom Prompt (Stretch)"; [owner-brief §4 Stretch].

- **Task [either track]: Final frozen held-out run**
  - **Status:** `TODO`
  - **Target date:** `2026-08-17`
  - Description: One run, no further tuning, against the frozen held-out set. Report honest metrics — this feeds Role 1's Demo Day metrics package.
  - Inputs: frozen set; stable recipes.
  - Deliverable: final metrics per recipe.
  - Depends on: week 3 hardening + this week's error fixes.
  - Reference: §12, §14 week 4 gate.

---

## Role 5 — Frontend developer/designer

Mandate: the spreadsheet UX is core product, not decoration — it has to hold up at hundreds of live-filling rows across multiple sheets, not just look right in a screenshot. Folder: `frontend/src/`. Primary references: §1, §2a, §4 step 7, §15.

### Week 1 (2026-07-22 – 2026-07-28)

- **Task: Grid skeleton**
  - **Status:** `TODO`
  - **Target date:** `2026-07-22`
  - Description: `components/grid/` — TanStack Table + virtual scroll, rows/columns rendering, basic sort/filter, source-context view stub. Can run against mocked/static data before Role 2's API is ready.
  - Inputs: none to start (mock data); real API later this week.
  - Deliverable: a grid that renders rows and columns.
  - Depends on: nothing blocking to start; switch to real API once Role 2's routes exist.
  - Reference: §1, §15.

- **Task: Rowspan-under-virtualization spike (§1 week-1 risk)**
  - **Status:** `TODO`
  - **Target date:** `2026-07-23`
  - Description: ARCHITECTURE.md §1 flags this explicitly as a week-1 spike, not a week-3 nice-to-have: confirm whether TanStack's virtual scroll can render a parent cell spanning its `inline`-expanded child band (§2a) when the span crosses the virtual window boundary. If it can't, the fallback is repeating the parent value per child row visually (storage is unaffected either way — parent cells are stored once regardless, §2a). Decide now so the recipe-builder/Expand UI (week 3) isn't designed against an assumption that doesn't hold.
  - Inputs: grid skeleton.
  - Deliverable: written spike result (rowspan works / fallback needed) feeding the week-3 Expand UI task.
  - Depends on: grid skeleton.
  - Reference: §1 "Week-1 spike", §2a.

- **Task: Generate TS API types from OpenAPI**
  - **Status:** `TODO`
  - **Target date:** `2026-07-24`
  - Description: Set up `openapi-typescript` (or equivalent) against Role 2's FastAPI-generated OpenAPI spec so frontend types don't hand-drift from backend schemas.
  - Inputs: Role 2's OpenAPI spec.
  - Deliverable: `types/` generated/kept in sync.
  - Depends on: Role 2's API routes existing.
  - Reference: tech-stack-decision.md "Shared FE/BE types."

- **Task: Wire to real backend for the week 1 gate**
  - **Status:** `TODO`
  - **Target date:** `2026-07-26`
  - Description: Once Role 2 has one recipe running through Preview→run→column→Result, point the grid at the real API so the week 1 gate is a real demo, not a mock.
  - Inputs: Role 2's API routes + first working recipe.
  - Deliverable: one real lot row's recipe result visible in the grid.
  - Depends on: Role 2.
  - Reference: §14 week 1 gate.

### Week 2 (2026-07-29 – 2026-08-04) — merges the original plan's weeks 2+3

- **Task: SSE hook + streaming cell fill**
  - **Status:** `TODO`
  - **Target date:** `2026-07-29`
  - Description: `hooks/` — subscribe to Role 2's SSE endpoint, update grid cells as they stream in, without re-rendering the whole grid per message (backend batches flushes, but the frontend must still apply them efficiently).
  - Inputs: Role 2's SSE endpoint.
  - Deliverable: cells visibly fill in live during a background run.
  - Depends on: Role 2's SSE task.
  - Reference: §4 step 7.

- **Task: Reconcile-on-reconnect**
  - **Status:** `TODO`
  - **Target date:** `2026-07-30`
  - Description: On reconnect, call Role 2's `?since=<version>` endpoint before resuming the live stream, so a dropped connection doesn't lose cell updates.
  - Inputs: Role 2's reconcile endpoint.
  - Deliverable: verified no data loss across a simulated disconnect.
  - Depends on: Role 2's reconcile task.
  - Reference: §4 step 7.

- **Task: Source/citation view (first pass)**
  - **Status:** `TODO`
  - **Target date:** `2026-07-31`
  - Description: `components/citations/` — clicking a cell opens its citation(s): source locator, quote, link back to the document/API field. Needs to handle the list-in-cell case (one citation per array item, not one per cell) eventually — first pass can handle single citations.
  - Inputs: Track A's citation data shape (Role 3/4) — coordinate on the `citation_jsonb` array format.
  - Deliverable: basic source view working.
  - Depends on: Role 3/4's citation anchoring landing enough to have real data to show.
  - Reference: §9.

- **Task: Recipe builder UI + Preview gate**
  - **Status:** `TODO`
  - **Target date:** `2026-08-02`
  - Description: `components/recipes/` — pick input column(s), pick a recipe, set params, run Preview on a stratified sample (§4 step 4 — not first-N), see preview results, confirm to run full background job. Surface the §2a list-gate rejection clearly when it fires (name the column, offer the two Expand modes) rather than a generic error. This is what Oksana uses for the week 2 gate (building a 2-column sequence herself), so usability here matters more than polish.
  - Inputs: Role 2's recipe/preview API.
  - Deliverable: a non-technical user can add a recipe and confirm a run without help.
  - Depends on: Role 2's API + at least 2 working recipes (Role 3/4).
  - Reference: §4 step 4, §2a.

- **Task: Typed status display (all eight) + feedback controls**
  - **Status:** `TODO`
  - **Target date:** `2026-08-04`
  - Description: Show all **eight** terminal statuses distinctly (not just "done"/"error") — rev. 3 adds `NotApplicable` alongside the original seven, and it must read visually distinct from `InsufficientData` (§5: "nothing to check" vs. "couldn't find"). Wire the correct/partial/incorrect/cannot-judge + relevance + error-type feedback form to Role 2's `cell_feedback` endpoint.
  - Inputs: Role 2's feedback endpoint; Role 1's rubric.
  - Deliverable: Oksana can leave feedback from the grid.
  - Depends on: Role 2's feedback API.
  - Reference: §5, §12.

### Week 3 (2026-08-05 – 2026-08-11)

- **Task: Sheet switcher UI**
  - **Status:** `TODO`
  - **Target date:** `2026-08-05`
  - Description: A case is now a set of sheets (§2a), not one grid — add tab/switcher navigation between the source `@tenders` sheet and derived sheets (Companies, Pairs) as they come online, each with its own columns/sort/filter state.
  - Inputs: Role 2's sheets API.
  - Deliverable: user can switch sheets within a case without losing per-sheet grid state.
  - Depends on: Role 2's sheets-aware API routes.
  - Reference: §2a.

- **Task: List-cell rendering + Expand UI**
  - **Status:** `TODO`
  - **Target date:** `2026-08-06`
  - Description: Render `value_type='list'` cells distinctly (count/preview of items, not a joined string), and surface the **Expand** action on a list column — the user picks `inline` or `new_table` (+ `dedup_by` for the latter), triggering Role 2's Expand recipe. Uses the week-1 rowspan spike result to decide how `inline` mode renders the parent-spans-children band.
  - Inputs: rowspan spike (week 1); Role 2's Expand recipe API.
  - Deliverable: a journalist can expand `@participants` into the Companies sheet from the grid, no manual API calls.
  - Depends on: rowspan spike, Role 2's Expand backend.
  - Reference: §2a.

- **Task: Cross-row signal + Pairs sheet display**
  - **Status:** `TODO`
  - **Target date:** `2026-08-07`
  - Description: Pairs now render as an ordinary sheet (via the sheet switcher) — sortable/scoreable/citable like any other. Separately, surface any remaining `cross_row_result` signals (narrowed scope, §8) in their own small panel with evidence and links to both source rows, since those genuinely have no row/sheet home.
  - Inputs: Role 3/4's Pair builder + Cross-row connect output; sheet switcher.
  - Deliverable: Pairs sheet browsable like any sheet; leftover cross-row signals visible and explorable.
  - Depends on: sheet switcher, Role 3/4.
  - Reference: §2a, §8.

- **Task: Result save + Google Sheets export UI**
  - **Status:** `TODO`
  - **Target date:** `2026-08-09`
  - Description: UI for saving the current grid slice as a Result (selected rows/columns/filters/version, per sheet) and triggering Role 2's multi-sheet Sheets export.
  - Inputs: Role 2's export endpoint.
  - Deliverable: working save + export on full volume, across sheets.
  - Depends on: Role 2.
  - Reference: [owner-brief §4 P0, §11], §2a.

### Week 4 (2026-08-12 – 2026-08-18) — merges the original plan's weeks 5+6, ends on Demo Day

- **Task: Stale-column UI**
  - **Status:** `TODO`
  - **Target date:** `2026-08-12`
  - Description: Grey out `stale` columns (via `column.status` rollup), show "new version available," require explicit user confirm before rerun — never auto-rerun. Confirm this reads correctly across a sheet boundary (an upstream edit on `@participants` marks the Companies sheet stale, §2a).
  - Inputs: Role 2's staleness walk (week 2).
  - Deliverable: correct stale/confirm UX, including cross-sheet staleness.
  - Depends on: Role 2.
  - Reference: §5, §4 "Staleness," §2a.

- **Task: Polish pass for solo Oksana run (week 4 gate)**
  - **Status:** `TODO`
  - **Target date:** `2026-08-15`
  - Description: Fix whatever UX friction blocks Oksana from running the full core loop *without developer help* — this is the literal week 4 gate (originally week 5's), now mid-week so there's runway left before Demo Day itself.
  - Inputs: feedback from Role 1's coordinated sessions.
  - Deliverable: gate met.
  - Depends on: all prior frontend tasks + Role 1's session scheduling.
  - Reference: §14 week 4 gate.

- **Task: Demo Day support**
  - **Status:** `TODO`
  - **Target date:** `2026-08-18`
  - Description: Be present/on-call for the live demo run, fix anything that breaks live, support the final Result save/export. If Demo Day slips into the buffer (§14a), this task slips with it.
  - Inputs: stable build.
  - Deliverable: clean live demo.
  - Depends on: everything else.
  - Reference: §14 week 4 gate.

---

## Buffer (2026-08-19 – 2026-08-28, ~1.5 weeks)

Deliberately **not** broken into per-role tasks here — see ARCHITECTURE.md §14a. This window is what the 6→4 week compression recovered; it is held back, not deleted. Two uses, in priority order:

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
- **Nothing in §13 (Deferred list)** — Merge, Recursive/Expand walk, Assistant Plan/Auto, fixed row-class taxonomy, Translation recipe/English UI, nested cases, multimedia, handwriting OCR, CMS/alerts — gets a task above, in a build week **or** the buffer. If someone finishes early, more P0 hardening beats starting a Deferred item.
