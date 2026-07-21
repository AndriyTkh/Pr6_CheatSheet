# CheatSheet — Project Task Plan

**Purpose:** split the 6-week pilot (owner brief §11, ARCHITECTURE.md §14) into role-owned task lists. One column per person/pair, ordered by week, each task self-contained (what to do, what you need first, what you hand off, where to read details).

**Source docs** (read before starting, and whenever a task references a `§`):
- `_docs/ARCHITECTURE.md` — **the** technical contract. All `§N` references below point here unless marked `[owner-brief §N]`.
- `_docs/archive/drive/Briefs & Vision/cheatsheet-owner-brief.md` — product/PM brief (Ukrainian), 6-week plan, acceptance criteria, canonical user scenario (§5), demo contract (§13).
- `_docs/tech-stack-decision.md` — why each tech pick, not just what.
- `_docs/repo-structure.md` — folder layout; every task below names the folder it lands in.
- `_docs/migrations/0001_core_schema.sql` — **locked** schema contract. Read-only for everyone except the backend/DB owner, and only changed via a new numbered migration + team agreement.
- `CLAUDE.md` (repo root) — read-order, git rules, and the progress-tracking convention this doc uses.

**People:**

| # | Role | One-line mandate |
|---|------|-------------------|
| 1 | **Coordinator — legal, data & stakeholder liaison** (owner/buyer + team member) | Gathers everything the builders need from outside the codebase: input files, API keys, Oksana's time and feedback, legal/compliance guardrails, journalist workflow examples, handover paperwork. |
| 2 | **Backend / DB developer** | Owns the Postgres schema, the DB access layer, the DAG/execution engine, and the API surface the frontend and recipes consume. |
| 3 & 4 | **Data Science / Agentic developers** (shared column — 2 people split the list) | One leans document scans/extraction (docling, OCR, chunking, citations, structured extract), the other leans agentic recipes (Web Search, Match & Verify, Cross-row connect). Both write recipes against the shared contract in `recipes/base.py`. |
| 5 | **Frontend developer/designer** | Grid UX, citation/source view, recipe builder + Preview UI, SSE streaming, sort/filter, Result/export. |

**Weekly gates** (must hold before moving on — ARCHITECTURE.md §14 / owner-brief §11). `Gate status` ∈ `PENDING` / `MET`, **edited only by the coordinator** — a week does not advance until its gate is `MET`:

| Wk | Gate | Gate status |
|---|---|---|
| 1 | One real row completes the whole core loop (connector → recipe → column → Result), no manual data substitution. | `PENDING` |
| 2 | Web Search produces a verifiable column on a representative subset. | `PENDING` |
| 3 | Oksana builds a ≥2-column recipe sequence herself. | `PENDING` |
| 4 | First Result is already useful in the pilot investigation. | `PENDING` |
| 5 | Oksana does the core loop solo; critical recipes pass agreed eval thresholds. | `PENDING` |
| 6 | End-to-end real-case run stands on its own (Demo Day). | `PENDING` |

**How to read a task:** Status → Description → Inputs (what must exist before you start) → Deliverable (what "done" looks like) → Depends on (who/what blocks you) → Reference (where to read the spec).

**Progress tracking (how this doc is used live):** each task carries a `Status` line — the single source of truth for that task. Tokens: `TODO` · `WIP` · `BLOCKED` · `REVIEW` · `DONE` (defined in `CLAUDE.md §3`). Update **only** the `Status` line of the task you own, optionally appending `@who branch/pr` or a blocker reason. Never reflow the rest of the doc — see `CLAUDE.md §5` for why. Don't start a task whose `Depends on` isn't `DONE`; if it's blocked, set `BLOCKED` with the reason so the coordinator can clear it.

---

## Role 1 — Coordinator: legal, data & stakeholder liaison

Mandate: you don't write product code. You keep the other four unblocked — real files, real access, real feedback, and you're the one who checks nothing in the pipeline breaks the "public data only" rule or leaves a secret somewhere it shouldn't be. Primary references: owner-brief §10–§12, §15; ARCHITECTURE.md §11.

### Week 1

- **Task: Run kickoff decisions to closure**
  - **Status:** `WIP` @marina
  - Description: Drive the 7 decisions owner-brief §12 requires before the team splits up: who owns which stream, when Oksana picks company X and is available for the first workflow session, what the row v0 unit is (ARCHITECTURE.md already proposes "one Prozorro tender package," §16 #3 — get it confirmed against real data, not just accepted on paper), which P0 recipe ships first, where the backlog lives and who makes product calls, what access/keys/quotas already exist vs. are missing, and what one-row end-to-end result the team commits to showing at the end of week 1.
  - Inputs: owner-brief §12, the team itself.
  - Deliverable: a short written decision log (backlog location is fine) covering all 7 points.
  - Depends on: nothing — this is the first task of the project.
  - Reference: [owner-brief §12].

- **Task: Build the access/dependency register**
  - **Status:** `WIP` @marina
  - Description: One document listing every external dependency the pilot touches: Prozorro API (public, no auth), YouControl API key + which licensed modules it actually covers (registry vs. metered add-ons — "having a key ≠ having all modules," §6a), OpenRouter key, Cloudflare R2 bucket/credentials, Railway project access, Google account(s) for Sheets/Docs export. For each: who holds it, where it's stored (never in the repo or client), what's still missing.
  - Inputs: whatever keys the team already has (owner-brief §10 notes YouControl's key already exists).
  - Deliverable: `dependency register` doc, kept current all 6 weeks.
  - Depends on: nothing to start; backend dev needs this register's contents (specifically the YouControl key) by end of week 1.
  - Reference: §6a, §11; [owner-brief §10, §12.6, §15 "API й ключі"].

- **Task: Hand off secrets server-side only**
  - **Status:** `DONE` @marina
  - Description: Get the YouControl key (and any other provider keys) to the backend developer through a private channel, never committed or pasted into shared docs/chat history that persists in the repo. Confirm with backend dev that the key lands behind one server-side proxy endpoint, not in frontend code or logs.
  - Inputs: keys from the dependency register.
  - Deliverable: confirmation the backend dev has what they need and it's not in git.
  - Depends on: dependency register task above; backend dev's connector work (Week 1/2, Role 2).
  - Reference: §11 "Secrets server-side only."

- **Task: Draft legal/compliance guardrails**
  - **Status:** `WIP` @marina
  - Description: Write the operating rules for what counts as "public data" for this pilot, what "external_ok" attestation means in practice for a manually-uploaded file (§11), and what Ukrainian personal-data-handling considerations apply to company officer/beneficiary data pulled from YouControl (names, addresses, EDRPOU) even though the source registry itself is public. This is the checklist backend/DS devs test against, not a legal memo nobody reads.
  - Inputs: ARCHITECTURE.md §11 (external_ok gate), owner-brief §10 ("Дані").
  - Deliverable: a short guardrails doc + a plain-language checklist for "can this document/field go to an external LLM/API provider?"
  - Depends on: nothing.
  - Reference: §11; [owner-brief §10].

- **Task: Run Oksana's first workflow session**
  - **Status:** `DONE` @marina — notes: [Excalidraw workflow](https://link.excalidraw.com/l/5iKoSi2GiB4/91hpw3JuCS)
  - Description: Schedule and sit in on Oksana walking through her *manual* process for the company-X case — this defines what a "logical row" needs to contain, what fields matter, and what failure states actually happen in practice (not just the ones in the doc). Capture it in writing/recording.
  - Inputs: Oksana's availability, company X chosen (may happen in this same session).
  - Deliverable: session notes handed to backend dev + DS/agentic pair — feeds row v0 confirmation and the first eval rubric.
  - Depends on: kickoff decisions task (company X pick).
  - Reference: [owner-brief §11 week 1, §5 canonical scenario].

- **Task: Draft the first eval rubric with Oksana**
  - **Status:** `TODO`
  - Description: Get Oksana's verdict categories (correct/partial/incorrect/cannot judge), relevance scale (0–3), and error-type taxonomy turned into a written rubric the eval track can wire up from day one.
  - Inputs: owner-brief §8/§12 feedback-form spec.
  - Deliverable: rubric doc, shared with DS/agentic pair (they wire `cell_feedback` capture to it).
  - Depends on: Oksana's first session.
  - Reference: §12; [owner-brief §8].

### Week 2

- **Task: Curate real input files for extraction/OCR testing**
  - **Status:** `TODO`
  - Description: Collect a batch of real tender documents (scanned PDFs included) that are legitimately public, covering the messy cases (no text layer, mixed language) the DS/document track needs to test docling/OCR against. Validate each file's public-source status against the Week 1 guardrails before handing it over.
  - Inputs: guardrails checklist; Prozorro document links.
  - Deliverable: a vetted sample file set + a short note on source/provenance for each.
  - Depends on: legal guardrails task; Prozorro connector live (Role 2/3-4) to pull real doc links.
  - Reference: §7, §11; [owner-brief §4 P0 "базовий OCR"].

- **Task: Run Oksana's vertical-slice review**
  - **Status:** `TODO`
  - Description: After week 2's connector volume ramp-up, get Oksana to look at real rows and give first-pass feedback (not formal eval yet — sanity check).
  - Inputs: rows in the grid (Role 2/5 output).
  - Deliverable: feedback notes routed to whichever track they concern.
  - Depends on: Week 2 gate (Web Search producing a verifiable column).
  - Reference: [owner-brief §11 week 2].

- **Task: Keep the dependency register current**
  - **Status:** `TODO`
  - Description: Add any new keys/quotas requested this week (embedding model, additional OpenRouter models, R2 bucket details).
  - Inputs: requests from backend/DS devs.
  - Deliverable: updated register.
  - Depends on: ongoing.
  - Reference: §11.

### Week 3

- **Task: Curate dev/held-out examples per recipe**
  - **Status:** `TODO`
  - Description: Work with Oksana to pick which real examples go into the tuning set vs. the frozen held-out set for each P0 recipe (Summarize, Classify/Score added this week). Held-out means held-out — no peeking to tune after it's frozen.
  - Inputs: recipe outputs from week 3; eval rubric.
  - Deliverable: labeled dev/held-out split, one per recipe, documented so nobody accidentally tunes on held-out.
  - Depends on: eval rubric (week 1); recipes live (Role 3-4).
  - Reference: §12; [owner-brief §8, §11 week 3].

- **Task: Run Oksana's 2-column-sequence session (week 3 gate)**
  - **Status:** `TODO`
  - Description: Sit Oksana down to build a ≥2-column recipe sequence herself — this *is* the week 3 gate, not just feedback. Capture friction points for frontend/recipe tracks.
  - Inputs: recipe builder UI (Role 5), ≥2 working recipes (Role 3-4).
  - Deliverable: gate confirmation + friction-point notes.
  - Depends on: frontend recipe builder, DS/agentic recipes reaching "usable" state.
  - Reference: [owner-brief §11 week 3 gate].

### Week 4

- **Task: Curate journalist workflow / pattern examples**
  - **Status:** `TODO`
  - Description: Turn owner-brief §3's pattern list (repeated participant groups, price anomalies, timing red flags, shared addresses/directors, etc.) into concrete annotated examples from the real dataset — this is what the DS/agentic pair tunes Classify/Score and Cross-row connect against, and what Oksana's feedback pass (below) references.
  - Inputs: real row data (by week 4 there should be hundreds); Oksana's domain knowledge.
  - Deliverable: annotated pattern-example doc.
  - Depends on: connector volume ramp-up (Role 2/3-4).
  - Reference: [owner-brief §3 "Що система може показати"].

- **Task: Coordinate Oksana's tuning feedback pass**
  - **Status:** `TODO`
  - Description: Get Oksana's marks on the cross-row signals and classification outputs so the DS/agentic pair can tune recipes this week, per the week 4 plan.
  - Inputs: cross-row connect output, Classify/Score output.
  - Deliverable: feedback logged in `cell_feedback` via the UI (Role 5) or relayed directly to Role 3-4.
  - Depends on: cross-row connect + classify/score working.
  - Reference: [owner-brief §11 week 4].

### Week 5

- **Task: Freeze the held-out set**
  - **Status:** `TODO`
  - Description: Lock the held-out examples with Oksana — no further tuning against them from this point. Confirm the dev track has actually stopped touching them.
  - Inputs: held-out set from week 3.
  - Deliverable: written confirmation of freeze date + scope.
  - Depends on: week 3 held-out task.
  - Reference: §12; [owner-brief §8, §11 week 5].

- **Task: Legal/security audit pass**
  - **Status:** `TODO`
  - Description: Verify (with backend dev) that no non-public material entered the pipeline, `external_ok` attestations are actually being checked and logged, and no secrets leaked into logs, the repo, or client-side code.
  - Inputs: guardrails checklist (week 1); backend dev's logging/proxy implementation.
  - Deliverable: audit sign-off or a punch list of fixes before Demo Day.
  - Depends on: backend security work (Role 2, §11 tasks).
  - Reference: §11; [owner-brief §11 week 5 "перевірка permissions, секретів"].

- **Task: Draft handover/IP documentation**
  - **Status:** `TODO`
  - Description: Per owner-brief §15's "handover doesn't happen" risk — write down (in draft form, finalize week 6) what transfers to Бабель: repo ownership, secrets/keys, hosting account, billing, domain, and who's the accepting owner on their side.
  - Inputs: dependency register; Railway/hosting account details from backend dev.
  - Deliverable: handover doc draft.
  - Depends on: dependency register being current.
  - Reference: [owner-brief §15 "Не відбудеться передача продукту"].

### Week 6 — Demo Day

- **Task: Prep and coordinate the live demo run**
  - **Status:** `TODO`
  - Description: Line up Oksana for the live run, prep a backup dataset/run in case of an external failure (API downtime, etc.) per the week 6 gate.
  - Inputs: frozen held-out set; stable build (Role 2/5).
  - Deliverable: demo runbook + backup dataset ready.
  - Depends on: everything else landing by end of week 5.
  - Reference: §14 week 6; [owner-brief §11 week 6, §13 demo contract].

- **Task: Finalize handover + "what's next" decision doc**
  - **Status:** `TODO`
  - Description: Close out the handover doc from week 5, and write up the Stop/Iterate/Operationalize/Expand recommendation per owner-brief §16.
  - Inputs: week 5 handover draft; demo results.
  - Deliverable: final handover package + decision memo.
  - Depends on: Demo Day run.
  - Reference: [owner-brief §16].

---

## Role 2 — Backend / DB developer

Mandate: the schema is already locked (`_docs/migrations/0001_core_schema.sql`) — your job is to build everything on top of it without drifting from it: ORM models, the DAG/execution engine, the job queue wiring, and the API the frontend and recipes call. Folder: `backend/app/`. Primary references: §2, §4, §11, §15.

### Week 1

- **Task: Mirror the locked schema into SQLAlchemy models**
  - **Status:** `TODO`
  - Description: Write async SQLAlchemy 2.0 models in `backend/app/models/` matching every table/enum in `0001_core_schema.sql` exactly. Do not add fields the migration doesn't have; do not edit the migration to match convenient ORM shapes — the migration is the contract (§2).
  - Inputs: `_docs/migrations/0001_core_schema.sql`.
  - Deliverable: `models/` populated, DB session (`db/session.py`) connecting to a real Postgres instance with `pgcrypto`/`vector` extensions enabled.
  - Depends on: nothing (migration already exists).
  - Reference: §2.

- **Task: Stand up FastAPI app skeleton + core config**
  - **Status:** `TODO`
  - Description: `main.py` entrypoint, `core/config.py` for settings (DB URL, OpenRouter key, R2 credentials, YouControl key — all from env, never hardcoded), basic health-check route.
  - Inputs: dependency register (Role 1) for what env vars/secrets to wire in.
  - Deliverable: app boots, connects to DB.
  - Depends on: Role 1 handing off the YouControl key + other secrets.
  - Reference: §15.

- **Task: Prozorro connector (row-producing)**
  - **Status:** `TODO`
  - Description: Implement `connectors/prozorro.py` per §6a — `GET /tenders` feed (cursor pagination, sync-by-`dateModified`), `GET /tenders/{id}`, documents list, deterministic winner extraction (`award.status='active'` → `suppliers[].identifier.id` = EDRPOU, `award.value`). No LLM — this is pure structured extraction. Wire it as the row-producing recipe (`recipes/row_producing/`).
  - Inputs: none (public API, no auth).
  - Deliverable: one real tender pulled end-to-end into a `row` with correct `provenance_jsonb` keyed by `tenderID`.
  - Depends on: models/DB task above.
  - Reference: §6, §6a, §16 #3.

- **Task: YouControl connector (cell-producing) + server-side key proxy**
  - **Status:** `TODO`
  - Description: Implement `connectors/youcontrol.py` per §6a — registry (USR) lookup by EDRPOU at minimum; note which metered add-on modules the license actually covers (confirm with Role 1's week-1 spike) before wiring recipes that assume them. Key lives server-side only, one proxy endpoint, rate-limited, logged without the secret itself.
  - Inputs: YouControl key from Role 1; module/license confirmation.
  - Deliverable: registry fields fillable on a row given an EDRPOU.
  - Depends on: Role 1's key handoff + module verification.
  - Reference: §6a, §11.

- **Task: Recipe contract (`recipes/base.py`)**
  - **Status:** `TODO`
  - Description: Implement the actual `Recipe` class per §3 — `id/name/version`, `exec_type` (func/agent), `input`/`params`/`output` schemas (JSON Schema, enforced server-side per §3's last bullet), `exec()`, `cite`, `eval`. This is the shared contract Role 3/4 build every recipe against — get it stable before they start writing recipes in parallel.
  - Inputs: none.
  - Deliverable: `Recipe` base class + schema-validation enforcement (bad JSON from an LLM → `Error`/`NeedsReview`, never a silent malformed value).
  - Depends on: nothing, but blocks Role 3/4's recipe work — prioritize this early in week 1.
  - Reference: §3.

- **Task: Minimal DAG engine — cycle check + topo sort**
  - **Status:** `TODO`
  - Description: `dag/` — cycle detection on `column_input` edge-add (reject edges that close a loop), topo-sort of the affected subgraph. Doesn't need wavefront-gated enqueue yet if week 1's single recipe run doesn't require it, but the cycle guard must exist before any column gets added.
  - Inputs: models task.
  - Deliverable: adding a column either succeeds or is rejected for cycles.
  - Depends on: models.
  - Reference: §4 steps 1–3.

- **Task: Get one recipe through Preview → run → column → Result (week 1 gate)**
  - **Status:** `TODO`
  - Description: Wire whichever P0 recipe the team picked (kickoff decision, Role 1) through the full loop on one real row: add column → preview → confirm → background run (can be synchronous for week 1, Procrastinate wiring can follow week 2) → cell filled → visible as a Result.
  - Inputs: Prozorro connector, recipe contract, at least a stub grid (Role 5) or direct DB inspection.
  - Deliverable: the literal week 1 gate.
  - Depends on: everything above in this week.
  - Reference: §14 week 1 gate.

### Week 2

- **Task: Wire Procrastinate as the real job queue**
  - **Status:** `TODO`
  - Description: `tasks/` — Procrastinate app + cell-execution task, backed by Postgres `LISTEN/NOTIFY` + `SKIP LOCKED`. `cell.status` stays data/display only, never the lock target (§4's explicit warning against a hand-rolled poller fighting the real queue).
  - Inputs: DAG engine (week 1).
  - Deliverable: cell jobs actually run through Procrastinate, not inline.
  - Depends on: week 1 DAG work.
  - Reference: §4, §15.

- **Task: Wavefront-gated enqueue + `cache_key`**
  - **Status:** `TODO`
  - Description: Implement §4 step 5 (blocked → enqueue on `LISTEN/NOTIFY` when inputs go terminal) and step 6 (`cache_key = hash(recipe_version + input_hashes + params + model_id + output_slot)`, force-refresh/cache-bust path for volatile recipes).
  - Inputs: Procrastinate wiring.
  - Deliverable: a cell never runs before its inputs are ready; identical inputs cache-hit.
  - Depends on: Procrastinate task.
  - Reference: §4 steps 5–6.

- **Task: SSE streaming with batched flush**
  - **Status:** `TODO`
  - Description: `realtime/` — stream cell updates to the frontend, coalesced (every 150–250ms or N cells, not one message per cell) to avoid re-render storms at pilot scale (~10-15k cells/case).
  - Inputs: wavefront enqueue producing terminal cells.
  - Deliverable: SSE endpoint the frontend can subscribe to.
  - Depends on: wavefront task.
  - Reference: §4 step 7.

- **Task: Reconcile-on-reconnect endpoint**
  - **Status:** `TODO`
  - Description: `GET /case/:id/cells?since=<version>` — monotonic `cell.version` lets a reconnecting client catch up before resuming the live stream.
  - Inputs: SSE task.
  - Deliverable: no cells silently lost across a disconnect.
  - Depends on: SSE task.
  - Reference: §4 step 7.

- **Task: Staleness walk on column edit**
  - **Status:** `TODO`
  - Description: The recursive CTE in §4 — mark downstream columns `stale` when an upstream one changes. Never auto-rerun; surface "new version available" for user confirm.
  - Inputs: DAG engine.
  - Deliverable: editing a column correctly greys dependents without silently recomputing them.
  - Depends on: DAG engine.
  - Reference: §4 "Staleness," §5.

- **Task: API routes for grid consumption**
  - **Status:** `TODO`
  - Description: `api/routes/` — cases, rows, columns, cells, recipes, runs, documents. This is the interface Role 5 builds the frontend against — get the shape stable and share it (OpenAPI schema, per tech-stack-decision.md's FE-type-generation plan) early.
  - Inputs: models.
  - Deliverable: routes returning real data; OpenAPI spec exportable for frontend TS type generation.
  - Depends on: models; blocks Role 5's real (non-mocked) integration.
  - Reference: §15 tech-stack-decision.md "Shared FE/BE types."

### Week 3

- **Task: Column-dependency support for derived-column inputs**
  - **Status:** `TODO`
  - Description: Recipes must accept already-derived columns as inputs (Summarize/Classify built on top of Web Search output, etc.) — confirm DAG/cache-key handle chained derivation correctly.
  - Inputs: week 2 DAG/cache work.
  - Deliverable: a 2+ column recipe chain runs correctly.
  - Depends on: week 2 DAG.
  - Reference: §4, §6.

- **Task: `cell_feedback` capture endpoint**
  - **Status:** `TODO`
  - Description: API route for the verdict/relevance/error-type/correct-value feedback form (§12), backing Oksana's 2-column-sequence session this week.
  - Inputs: eval rubric (Role 1).
  - Deliverable: feedback persists to `cell_feedback`.
  - Depends on: Role 1's rubric.
  - Reference: §12.

### Week 4

- **Task: Dead-end lock**
  - **Status:** `TODO`
  - Description: §6's engine feature — terminal-empty cells (`NotFound`/`InsufficientData`/`SourceUnavailable`) propagate `InsufficientData` downstream without enqueueing, negative-cached on `cache_key` so identical inputs don't re-hit a paid provider.
  - Inputs: cache-key infra (week 2).
  - Deliverable: cost-safety verified — a known-empty chain doesn't re-spend.
  - Depends on: week 2 cache work.
  - Reference: §6.

- **Task: Google Sheets export**
  - **Status:** `TODO`
  - Description: Export current grid view (rows/columns/filters) to Google Sheets on full volume, per week 4 plan.
  - Inputs: stable API routes.
  - Deliverable: working export on the real dataset.
  - Depends on: API routes.
  - Reference: [owner-brief §4 P0, §11 week 4].

### Week 5

- **Task: Idempotency cache on external calls**
  - **Status:** `TODO`
  - Description: §11's crash-retry protection — short-TTL idempotency cache keyed `(recipe_version, row_id, column_id, call_args_hash)` on the server-side provider proxy, so a Procrastinate retry after a crash doesn't double-charge YouControl/LLM quota.
  - Inputs: connector proxy (week 1).
  - Deliverable: verified no double-charge on a simulated crash-retry.
  - Depends on: connector work.
  - Reference: §11.

- **Task: `external_ok` gate enforcement**
  - **Status:** `TODO`
  - Description: Every recipe dispatch checks `external_ok` on every source document in `row_context`; any un-attested document blocks the run with a clear message, never a silent send.
  - Inputs: legal guardrails (Role 1).
  - Deliverable: verified block on an unattested-upload test case.
  - Depends on: Role 1 guardrails doc; feeds Role 1's security audit.
  - Reference: §11.

- **Task: Cost cap + permissions/security hardening pass**
  - **Status:** `TODO`
  - Description: Verify case privacy defaults, role checks (owner/editor/viewer), no secrets in logs, cost caps active before full runs.
  - Inputs: audit checklist (Role 1).
  - Deliverable: sign-off from Role 1's audit task.
  - Depends on: Role 1 audit task (mutual).
  - Reference: §11.

### Week 6

- **Task: Freeze version, support the final held-out run + live demo**
  - **Status:** `TODO`
  - Description: Tag/freeze the build, support the final frozen-held-out run and the live Demo Day run technically.
  - Inputs: everything else.
  - Deliverable: stable, demoed system; handover-ready repo/infra state for Role 1's handover doc.
  - Depends on: all prior weeks.
  - Reference: §14 week 6.

---

## Role 3 & 4 — Data Science / Agentic developers (shared column)

Two people, one list — split by whichever half fits each person better, but keep both halves moving in parallel since they share the recipe contract (`recipes/base.py`, owned by Role 2) and the same eval loop (§12). **Track A: document scans/extraction.** **Track B: agentic recipes.** Folder: `backend/app/documents/`, `backend/app/citations/`, `backend/app/agents/`, `backend/app/recipes/`. Each task is tagged `[Track A]` / `[Track B]` / `[either track]` so the two of you edit different `Status` lines — never the same one.

### Week 1

- **Task [either track]: Recipe catalog stubs against the contract**
  - **Status:** `TODO`
  - Description: Once Role 2 ships `recipes/base.py`, stub out the P0 recipe classes (§6 table) in `recipes/cell_producing/`, `recipes/row_producing/`, `recipes/cross_row/` so both people can build in parallel without stepping on each other. Pick and fully implement the recipe the team chose in the kickoff decision (Role 1 task) first — that's the week 1 gate.
  - Inputs: `recipes/base.py` (Role 2).
  - Deliverable: stubs exist; the chosen first recipe works end to end.
  - Depends on: Role 2's recipe contract.
  - Reference: §3, §6.

- **Task [Track A — docs]: docling ingest pipeline**
  - **Status:** `TODO`
  - Description: `documents/` — wire docling for PDF/DOCX/XLSX/PPTX/HTML parsing, text-layer check before OCR, Tesseract backend (ukr+rus+eng traineddata) only on pages that actually lack a text layer. No raw pytesseract calls outside docling.
  - Inputs: sample files (Role 1, arrives week 2, but Prozorro connector docs can be a first source in week 1).
  - Deliverable: a manually-uploaded or Prozorro-sourced doc parses into normalized content + per-element page/bbox.
  - Depends on: Role 2's Prozorro connector for doc links, or Role 1's manual samples.
  - Reference: §7, §9, §15.

- **Task [Track B — agentic]: Web Search recipe skeleton**
  - **Status:** `TODO`
  - Description: Tool-using loop, row-scoped: build query from selected columns, call search tool, select relevant results, explain the choice. Output schema per §3 (JSON-schema enforced).
  - Inputs: recipe contract; OpenRouter access (dependency register, Role 1).
  - Deliverable: a stub that runs and returns a typed, cited result on one row.
  - Depends on: Role 2's recipe contract + OpenRouter key.
  - Reference: §6, §8.

### Week 2

- **Task [Track A]: Chunking + embeddings**
  - **Status:** `TODO`
  - Description: Chunk parsed documents, embed with a pinned embedding model (`embed_model_id` recorded per chunk, §10 — never a floating model), store in `pgvector`.
  - Inputs: docling pipeline.
  - Deliverable: chunks + embeddings queryable.
  - Depends on: docling task.
  - Reference: §7, §10.

- **Task [Track A]: Citation quote→locate anchoring**
  - **Status:** `TODO`
  - Description: `citations/` — model/extraction returns a verbatim quote, code string-searches it back into the source for the offset. Never trust a model-reported page number. Add fuzzy locate (normalize + token-window/edit-distance) for OCR'd text, with `match_confidence`; below threshold → `NeedsReview`, don't store a guessed offset.
  - Inputs: chunking task; docling per-element page/bbox.
  - Deliverable: citations resolve to a real, verifiable location for both clean-text and OCR'd docs.
  - Depends on: chunking + docling tasks.
  - Reference: §9.

- **Task [Track B]: Stabilize Web Search into a verifiable column (week 2 gate)**
  - **Status:** `TODO`
  - Description: This is the literal week 2 gate — Web Search must produce a column Oksana/Role 1 can actually verify against citations on a representative subset of rows.
  - Inputs: Web Search skeleton (week 1); citation anchoring (Track A, ideally landed by now — coordinate).
  - Deliverable: gate met.
  - Depends on: Track A's citation work landing in parallel.
  - Reference: §14 week 2 gate.

- **Task [Track B]: Match & Verify recipe**
  - **Status:** `TODO`
  - Description: Agent loop, row-scoped, fixed tool = YouControl: choose search strategy (EDRPOU → name → person) → call → compare to row data → typed status + explanation + sources.
  - Inputs: YouControl connector (Role 2).
  - Deliverable: working recipe on real rows.
  - Depends on: Role 2's YouControl connector.
  - Reference: §6, §8.

### Week 3

- **Task [either track]: Summarize recipe**
  - **Status:** `TODO`
  - Description: LLM recipe, text column → short column, citation-entailment checked at eval time. Must accept a derived column as input (e.g. Web Search output) — confirm with Role 2's column-dependency work.
  - Inputs: recipe contract; citation anchoring.
  - Deliverable: working recipe.
  - Depends on: Role 2's derived-column-input support.
  - Reference: §6.

- **Task [either track]: Classify/Score recipe**
  - **Status:** `TODO`
  - Description: LLM recipe against a transparent rubric (Oksana-defined, per Role 1's rubric task), typed label/score output.
  - Inputs: eval rubric (Role 1).
  - Deliverable: working recipe.
  - Depends on: Role 1's rubric.
  - Reference: §6.

- **Task [Track A]: Structured Extract — lazy/hybrid**
  - **Status:** `TODO`
  - Description: Deterministic extraction from already-structured connector data (no LLM); LLM only for unstructured fragments inside a row, on-demand per §7's "hybrid, lazy default" — explicitly not eager full-JSON extraction.
  - Inputs: docling pipeline; connector data.
  - Deliverable: working recipe, both the deterministic and LLM-lazy paths.
  - Depends on: docling + connectors.
  - Reference: §7.

- **Task [either track]: dev/held-out wiring per recipe**
  - **Status:** `TODO`
  - Description: Make sure each recipe's eval path can run against the dev/held-out split Role 1 is curating this week.
  - Inputs: Role 1's split.
  - Deliverable: eval runnable per recipe.
  - Depends on: Role 1.
  - Reference: §12.

### Week 4

- **Task [either track]: Deterministic comparisons (Aggregate/Fold, Compare/Diff)**
  - **Status:** `TODO`
  - Description: Code-based (not LLM) recipes finding repeated companies/attributes/patterns — exact counts and matches are code, per §3's "not everything is an LLM" rule.
  - Inputs: real volume of rows.
  - Deliverable: working recipes surfacing repeated participants/attributes.
  - Depends on: connector volume (Role 2).
  - Reference: §3, §6.

- **Task [Track B]: Cross-row connect**
  - **Status:** `TODO`
  - Description: Two-phase — deterministic candidate-gen (block on shared phone/email/address/EDRPOU/director/owner to cut N² to a handful), then agentic verify per candidate pair (compare, explore YouControl/web, typed status + evidence citing the shared attribute *and* both source records). Writes to `cross_row_result`, not a grid cell.
  - Inputs: candidate attributes available on rows (connector data); Match & Verify patterns reusable here.
  - Deliverable: signal generation on real row pairs, with evidence.
  - Depends on: sufficient row volume + registry data.
  - Reference: §8.

- **Task [either track]: Tune recipes on Oksana's marks**
  - **Status:** `TODO`
  - Description: Use Role 1's curated pattern examples + Oksana's feedback pass to adjust prompts/rubrics on Classify/Score and Cross-row connect.
  - Inputs: Role 1's pattern-example doc + feedback.
  - Deliverable: measurably improved eval numbers on the dev set.
  - Depends on: Role 1's week 4 tasks.
  - Reference: §12.

### Week 5

- **Task [either track]: Run against dev/validation only, fix errors found**
  - **Status:** `TODO`
  - Description: Fix citation mismatches, source errors, stale-dependency bugs surfaced by hardening runs. Do not touch the frozen held-out set.
  - Inputs: frozen held-out boundary (Role 1).
  - Deliverable: error list closed out or triaged.
  - Depends on: Role 1's freeze.
  - Reference: [owner-brief §11 week 5].

- **Task [Stretch, if capacity allows]: Custom Prompt recipe**
  - **Status:** `TODO`
  - Description: Only after the above is solid — free-form prompt as its own recipe, per-use rubric.
  - Inputs: spare capacity.
  - Deliverable: working Stretch recipe.
  - Depends on: everything else in week 5 being done first.
  - Reference: §6 "Custom Prompt (Stretch)"; [owner-brief §4 Stretch].

### Week 6

- **Task [either track]: Final frozen held-out run**
  - **Status:** `TODO`
  - Description: One run, no further tuning, against the frozen held-out set. Report honest metrics — this feeds Role 1's Demo Day metrics package.
  - Inputs: frozen set; stable recipes.
  - Deliverable: final metrics per recipe.
  - Depends on: week 5 hardening.
  - Reference: §12, §14 week 6.

---

## Role 5 — Frontend developer/designer

Mandate: the spreadsheet UX is core product, not decoration — it has to hold up at hundreds of live-filling rows, not just look right in a screenshot. Folder: `frontend/src/`. Primary references: §1, §4 step 7, §15.

### Week 1

- **Task: Grid skeleton**
  - **Status:** `TODO`
  - Description: `components/grid/` — TanStack Table + virtual scroll, rows/columns rendering, basic sort/filter, source-context view stub. Can run against mocked/static data before Role 2's API is ready.
  - Inputs: none to start (mock data); real API later this week.
  - Deliverable: a grid that renders rows and columns.
  - Depends on: nothing blocking to start; switch to real API once Role 2's routes exist.
  - Reference: §1, §15.

- **Task: Wire to real backend for the week 1 gate**
  - **Status:** `TODO`
  - Description: Once Role 2 has one recipe running through Preview→run→column→Result, point the grid at the real API so the week 1 gate is a real demo, not a mock.
  - Inputs: Role 2's API routes + first working recipe.
  - Deliverable: one real row's recipe result visible in the grid.
  - Depends on: Role 2.
  - Reference: §14 week 1 gate.

- **Task: Generate TS API types from OpenAPI**
  - **Status:** `TODO`
  - Description: Set up `openapi-typescript` (or equivalent) against Role 2's FastAPI-generated OpenAPI spec so frontend types don't hand-drift from backend schemas.
  - Inputs: Role 2's OpenAPI spec.
  - Deliverable: `types/` generated/kept in sync.
  - Depends on: Role 2's API routes existing.
  - Reference: tech-stack-decision.md "Shared FE/BE types."

### Week 2

- **Task: SSE hook + streaming cell fill**
  - **Status:** `TODO`
  - Description: `hooks/` — subscribe to Role 2's SSE endpoint, update grid cells as they stream in, without re-rendering the whole grid per message (backend batches flushes, but the frontend must still apply them efficiently).
  - Inputs: Role 2's SSE endpoint.
  - Deliverable: cells visibly fill in live during a background run.
  - Depends on: Role 2's SSE task.
  - Reference: §4 step 7.

- **Task: Reconcile-on-reconnect**
  - **Status:** `TODO`
  - Description: On reconnect, call Role 2's `?since=<version>` endpoint before resuming the live stream, so a dropped connection doesn't lose cell updates.
  - Inputs: Role 2's reconcile endpoint.
  - Deliverable: verified no data loss across a simulated disconnect.
  - Depends on: Role 2's reconcile task.
  - Reference: §4 step 7.

- **Task: Source/citation view (first pass)**
  - **Status:** `TODO`
  - Description: `components/citations/` — clicking a cell opens its citation(s): source locator, quote, link back to the document/API field. Needs to handle the list-in-cell case (one citation per array item, not one per cell) eventually — first pass can handle single citations.
  - Inputs: Track A's citation data shape (Role 3/4) — coordinate on the `citation_jsonb` array format.
  - Deliverable: basic source view working.
  - Depends on: Role 3/4's citation anchoring landing enough to have real data to show.
  - Reference: §9.

### Week 3

- **Task: Recipe builder UI + Preview gate**
  - **Status:** `TODO`
  - Description: `components/recipes/` — pick input column(s), pick a recipe, set params, run Preview on a stratified sample (§4 step 4 — not first-N), see preview results, confirm to run full background job. This is what Oksana uses for the week 3 gate (building a 2-column sequence herself), so usability here matters more than polish.
  - Inputs: Role 2's recipe/preview API.
  - Deliverable: a non-technical user can add a recipe and confirm a run without help.
  - Depends on: Role 2's API + at least 2 working recipes (Role 3/4).
  - Reference: §4 step 4.

- **Task: Typed status display + feedback controls**
  - **Status:** `TODO`
  - Description: Show the seven terminal statuses distinctly (not just "done"/"error"), and wire the correct/partial/incorrect/cannot-judge + relevance + error-type feedback form to Role 2's `cell_feedback` endpoint.
  - Inputs: Role 2's feedback endpoint; Role 1's rubric.
  - Deliverable: Oksana can leave feedback from the grid.
  - Depends on: Role 2's feedback API.
  - Reference: §5, §12.

### Week 4

- **Task: Cross-row signal display**
  - **Status:** `TODO`
  - Description: Surface `cross_row_result` signals somewhere sensible in the UI (they're not grid cells — need their own view/panel) with evidence and links to both source rows.
  - Inputs: Role 3/4's cross-row connect output.
  - Deliverable: signals visible and explorable.
  - Depends on: Role 3/4.
  - Reference: §8.

- **Task: Result save + Google Sheets export UI**
  - **Status:** `TODO`
  - Description: UI for saving the current grid slice as a Result (selected rows/columns/filters/version) and triggering Role 2's Sheets export.
  - Inputs: Role 2's export endpoint.
  - Deliverable: working save + export on full volume.
  - Depends on: Role 2.
  - Reference: [owner-brief §4 P0, §11 week 4].

### Week 5

- **Task: Stale-column UI**
  - **Status:** `TODO`
  - Description: Grey out `stale` columns (via `column.status` rollup), show "new version available," require explicit user confirm before rerun — never auto-rerun.
  - Inputs: Role 2's staleness walk (week 2).
  - Deliverable: correct stale/confirm UX.
  - Depends on: Role 2.
  - Reference: §5, §4 "Staleness."

- **Task: Polish pass for solo Oksana run (week 5 gate)**
  - **Status:** `TODO`
  - Description: Fix whatever UX friction blocks Oksana from running the full core loop *without developer help* — this is the literal week 5 gate.
  - Inputs: feedback from Role 1's coordinated sessions.
  - Deliverable: gate met.
  - Depends on: all prior frontend tasks + Role 1's session scheduling.
  - Reference: §14 week 5 gate.

### Week 6

- **Task: Demo Day support**
  - **Status:** `TODO`
  - Description: Be present/on-call for the live demo run, fix anything that breaks live, support the final Result save/export.
  - Inputs: stable build.
  - Deliverable: clean live demo.
  - Depends on: everything else.
  - Reference: §14 week 6.

---

## Cross-role dependency notes

- **Everyone blocks on Role 2's `recipes/base.py`** (week 1) before writing real recipes — Role 2 should prioritize that class first, even ahead of the full DAG engine, so Role 3/4 aren't idle.
- **Role 3/4's citation anchoring blocks Role 5's source view** — coordinate the `citation_jsonb` array shape directly between these tracks early, don't wait for it to surface as a mismatch in week 2.
- **Role 1's key handoff blocks Role 2's YouControl connector**, which in turn blocks Role 3/4's Match & Verify and Role 5's registry-field display. Get the key handoff done in the first two days of week 1.
- **Role 1's eval rubric blocks Classify/Score (Role 3/4) and the feedback UI (Role 5)** — needed by week 3, so start it week 1.
- **Nothing in §13 (Deferred list)** — Merge, Recursive/Expand walk, Assistant Plan/Auto, fixed row-class taxonomy, nested cases, multimedia, handwriting OCR, CMS/alerts — gets a task above. If someone finishes early, more P0 hardening beats starting a Deferred item.
