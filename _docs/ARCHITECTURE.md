# CheatSheet — Technical Architecture Plan

**Status:** working draft (rev. 2 — engine-correctness pass) · derived from `_docs/archive/rough-outline.md` + product/owner briefs
**Scope:** summer pilot vertical slice (Prozorro + YouControl, company-X tender case)
**This is the technical contract.** Every `§N` reference in `TASKS.md` and the other docs points here. Who-does-what-when lives in `_docs/TASKS.md`; read-order and git rules in `CLAUDE.md`.

---

## 0. Core idea in one line

CheatSheet is a **columnar, lineage-tracked compute graph over rows**, where each column is the memoized output of a versioned operation ("recipe"), and every cell carries provenance and a typed status. Spreadsheet on the surface; a build-system/DAG engine underneath.

Get this engine **generic** (row / column / recipe / run / result know nothing about tenders). Prozorro and YouControl are just connectors. This is the single most important constraint — it protects against the "tender pipeline instead of a product" failure.

---

## 1. Components

| # | Component | Choice | Notes |
|---|-----------|--------|-------|
| 1 | Database | **Postgres** (+ `pgvector`, `jsonb`) | One source of truth. DAG, cells, chunks, provenance, eval — all here. No second DB. |
| 2 | Recipe format | N input cols → M output cols; `func` or `agent`; versioned | Generality **is** the product. |
| 3 | Task runner | **Procrastinate** (Postgres `LISTEN/NOTIFY` + `SKIP LOCKED`), wavefront-gated per cell → Redis/Celery only if scale hits | One queue. `cell.status` is data, not the lock target. See §4. |
| 4 | UI | **TanStack Table + virtual scroll**, streaming cell updates (SSE + reconcile-on-reconnect) | Headless grid, own the render, handles 100s of rows filling live. |
| 5 | One-pass recipes | WebSearch, Connector(API), Structured Extract, Summarize, Classify/Score, Aggregate/Fold, Compare/Diff, Generate/Seed rows, Custom Prompt | The recipe catalog (§6): cell-producing, row-producing, cross-row. |
| 6 | Provenance / citations | quote→locate anchoring, source-language, per emitted item | Product soul. Principle 2. See §9. |
| 7 | Versioning + staleness | `recipe_version`, `cache_key`, DAG staleness walk | Principle 5. |
| 8 | Eval hooks | per-recipe metrics + cell-level human feedback | Oksana = ground truth. Wire from week 1. |
| 9 | Document processing | 3 distinct modes (retrieve / enumerate / extract) | See §7. |
| 10 | Agentic | bounded (WebSearch, Match&Verify, explicit cross-row) | Unbounded Assistant Plan/Auto = Deferred. See §8. |

---

## 2. Data model (Postgres)

**Locked Day 1-2. Committed migration: `migrations/0001_core_schema.sql`** — that file is the frozen contract; this section is its map. Change only by team agreement + a new numbered migration.

| Table | Grain | Key columns | Notes |
|---|---|---|---|
| `case` | one investigation | `owner_id`, `is_private` (default true) | §11 private by default |
| `case_member` | (case, user) | `role` ∈ owner/editor/viewer | §11 (reviewer = Stretch) |
| `recipe` | (id, **version**) | `exec_type` func/agent, `shape` cell/row/cross_row, `volatile`, `params_schema`, `output_schema` (JSON Schema), `cite_spec`, `eval_spec` | §3. Old results stay pinned to the exact version; never mutate a shipped one. |
| `row` | one **tender package** (§16 #3) | `origin` connector/upload/generated, `provenance_jsonb` (keyed by `tenderID`), `generated_by_run_id`, `state`†, `merged_into_row_id`† | †dormant — P0 always `active` (§5) |
| `column` | one derived (or source) column | `recipe_id`+`recipe_version`, `output_slot`, `params_jsonb`, `output_lang`, `status` (rollup) | source/seed columns have NULL recipe |
| `column_input` | DAG edge | `(column_id, input_column_id)` | acyclicity enforced in app at edge-add (§4 step2); CTE walks staleness/lineage |
| `cell` | (row, column) | `value_jsonb` (may be list), `status` (`cell_status` enum), `citation_jsonb` (array, §9), `cache_key`, `run_id`, `version` (monotonic, for SSE `?since=`), `terminal_scope`† | the memoized result; `cache_key` app-computed (§4 step6) |
| `run` | one execution | `model_id` (pinned), `provider_endpoint`, `prompt_hash`, `used_fallback`, `cache_bust`, `cost_usd` | §10 provenance log |
| `document` | one source file/API doc | `row_id`, `external_ok` (hard gate §11), `source_lang`, `ocr_status`, `storage_key` (R2) | §7/§9/§11 |
| `chunk` | one text chunk | `embedding vector(1024)`, `embed_model_id` (pinned), `page`, `char_start/end` | §10 same-model-only retrieval; ANN index added wk2 |
| `cross_row_result` | one pairwise signal | `row_ids[]`, `column_ids[]`, `signal`, `evidence_jsonb`, `input_versions_jsonb`, `is_stale` | §8/§16 #6 — outside the DAG, preserves row isolation |
| `cell_feedback` | one human verdict | `verdict`, `relevance` 0-3, `error_type`, `correct_value`, `judge_id` | §12 eval |

**Enums (locked):** `cell_status` (§5 — one enum spanning `blocked/pending/running` + the seven terminals + dormant `Rejected`), `column_status` (`pending/running/partial/done/stale`), `recipe_exec_type`, `recipe_shape`, `row_origin`, `row_state`†, `terminal_scope`†, `case_role`.

---

## 3. Recipe format

A recipe is a **pure-ish function signature** wrapped in versioning metadata:

```
Recipe {
  id, name, version
  exec_type:     func | agent
  input:         list of column refs (N ≥ 1)
  params:        typed schema (rubric, target entity, language, model_id, …)
  output:        typed schema (M ≥ 1 columns) + per-cell status enum
  exec():        (row_context, params) → [{value, status, citation}]
  cite:          how each value anchors to a source
  eval:          which metrics apply
}
```

Rules:
- **Engine is N→M from day 1** (data model). First shipped *recipe* may be 1→1 (scope ramp). Don't confuse the two — one is permanent, one is temporary.
- A recipe never reaches outside `row_context`. The framework **assembles** the context and hands it in, so isolation is structural, not a coding convention.
- `func` = deterministic (API extract, counts, pattern match). `agent` = tool-using LLM loop. Same signature, same eval, same logging.
- Not everything is an LLM. Exact counts / frequencies / matches → code (owner brief §9).
- **`output` is a JSON Schema, and it is enforced at the model edge.** LLM recipes constrain generation with provider structured-output / function-calling to that schema, then the framework **validates the returned JSON against it server-side**. Validation failure → cell status `Error` (or `NeedsReview`) carrying the validation message — never a silent malformed `value_jsonb`. This is where Principle 4 ("uncertainty is data, not an empty cell") is enforced, not just declared.

---

## 4. Execution + DAG

**Flow when user adds a recipe:**
1. New column node + edges (`column_input`).
2. **Cycle check** (DFS/Kahn) — reject if the new edge closes a loop. Keeps graph acyclic.
3. Topo-sort the affected subgraph.
4. **Preview** on a few rows (gate before spend). Sample **stratified**, not first-N — a few connector-flagged hard/edge rows + a few random — so an easy sample doesn't give false confidence. Preview rows run for real; on confirm they **cache-hit** (same `cache_key`) instead of re-spending.
5. On confirm → **wavefront-gated enqueue** (topo order of *enqueue* ≠ topo order of *execution* under parallel workers, so ordering must be enforced by data, not queue insertion order):
   - For each row: if all input cells are already terminal → enqueue the cell job now; else insert the cell as `status='blocked'`.
   - When any cell reaches a terminal status, `LISTEN/NOTIFY` fires → re-check `blocked` cells in the *same row* whose column depends on the just-finished column → enqueue those now ready. A cell never runs before its inputs are ready.
   - Skip rows where `row.state != 'active'` (dormant in P0 — all rows are `active` until deferred Merge/gating ships).
6. Each cell: compute `cache_key = hash(recipe_version + resolved_input_hashes + params + model_id + output_slot)`. The **`output_slot`** term is what keeps a 1→M recipe's M columns from colliding on one key. Cache hit → skip. Miss → run → write `value + status + citation + run_id`.
   - **Force-refresh (cache-bust):** `volatile` recipes (agent/web/LLM, §2) never re-query on identical inputs otherwise. A user (or a stale-column confirm) can invalidate a single cell → `status='pending'` + a `cache_bust` flag on the job → that one cell bypasses cache, writes a **new** `run` (old run retained in the log → Principle 5 history). No `recipe_version` bump needed to re-run one row.
7. Fill streams into the grid in the background; partial failures are visible.
   - At pilot ceiling (~10-15k cells/case), don't push one SSE message per completed cell — batch/coalesce flushes (e.g. every 150-250ms or N cells) so the grid isn't re-rendering thousands of times in a burst.
   - **Reconnect has no replay by itself.** Each streamed update carries a monotonic version. On reconnect the client issues one `GET /case/:id/cells?since=<version>` reconcile-fetch, then resumes the live stream — so cells that filled during a multi-minute disconnect are not silently lost.

**Staleness (upstream edited):** walk edges *downstream*, mark reachable columns `stale`. **Do not auto-rerun** — surface "new version available", user confirms.

```sql
-- staleness: walk down
WITH RECURSIVE stale AS (
  SELECT column_id FROM column_input WHERE input_column_id = :changed
  UNION
  SELECT ci.column_id FROM column_input ci JOIN stale s ON ci.input_column_id = s.column_id
)
UPDATE column SET status='stale' WHERE id IN (SELECT column_id FROM stale);

-- lineage: walk up (flip the join)
WITH RECURSIVE origin AS (
  SELECT input_column_id FROM column_input WHERE column_id = :target
  UNION
  SELECT ci.input_column_id FROM column_input ci JOIN origin o ON ci.column_id = o.input_column_id
)
SELECT * FROM column WHERE id IN (SELECT input_column_id FROM origin);
```

Use `UNION` (not `UNION ALL`) so diamonds/accidental cycles terminate.

**One queue — Procrastinate, not a hand-rolled poller.** Procrastinate *is* the Postgres `LISTEN/NOTIFY` + `SKIP LOCKED` queue (tech-stack §15); do not also poll `cell.status` for locking — that would be two queues fighting. `cell.status` is **data/display** (`blocked → pending → running → <terminal enum>`), never the lock target. Procrastinate owns the job: on pick it flips the cell to `running`; on finish it writes `value + status + citation + run_id`. Wavefront readiness (step 5) decides *when* a cell's job is created; Procrastinate decides *which worker* runs it. Enough for pilot scale (10-15k cells/case); promote to Redis/Celery only on an order-of-magnitude load jump.

---

## 5. Typed cell status

Never a nullable string. Enum (Principle 4 — uncertainty is data). **P0 active set = the owner brief's seven** (brief §6):

`Answered · InsufficientData · NotFound · SourceUnavailable · ConflictingEvidence · Error · NeedsReview`

Status describes the result of *one operation*. "Not found" ≠ "the fact doesn't exist in the world."

**Column status is a rollup, not a second source of truth.** `cell.status` is the per-operation truth (the enum above). `column.status` is *derived* from its cells + version state — `pending / running / partial / done / stale` — where `partial` = some cells terminal-error while others Answered. The grid greys a `stale` column by joining `column.status`; cells keep their old values and citations until a confirmed rerun (§4).

**Deferred (dormant schema, not P0 behavior):** `Rejected` status + `terminal_scope='row'` + `row.state`/`merged_into_row_id` exist in the schema (§2) only for the deferred Merge / row-gating features (§8). In P0 every row stays `active`, no recipe locks a row, and `Rejected` is never emitted — row lifecycle is a single-state axis until those features ship.

---

## 6. Recipe catalog (P0)

Three shapes, one contract (§3): **cell-producing** (N cols → M cols over existing rows), **row-producing** (emit new rows), **cross-row** (→ `cross_row_result`, no single-row home). Same `exec()`/`cite`/`eval` metadata for all three.

**Shape is a property of the recipe, not the connector.** A connector can back a recipe of either shape — Prozorro is row-producing in P0 (search params → tender rows) but a `Connector: Prozorro (fields)` cell-producing variant (tenderID in row → fill fields) is equally valid on the same contract. Symmetrically, YouControl is cell-producing in P0 (EDRPOU in row → registry fields) but a row-producing YouControl variant (founders/beneficiaries/group → **new company rows**) is the same connector, opposite direction — that variant *is* the deferred **Recursive/Expand walk** (§13): depth-iteration, not single-pass, so it stays out of P0. When Expand walk ships it reuses this contract, no new plumbing.

**Cell-producing:**

| Recipe | exec | Input → Output | Eval metric |
|--------|------|----------------|-------------|
| **Connector: YouControl** | func | company key (EDRPOU) → registry fields | success rate, match accuracy on human sample |
| **Structured Extract** | func + LLM | doc/fields → typed columns (deterministic from API; LLM only for unstructured fragments) | precision/recall/F1 on critical fields |
| **Web Search** | agent | query cols → external-context column | precision@k, authoritative-source share, dup/broken-link rate |
| **Summarize** | LLM | text col → short column | citation-entailment rate, unsupported-claim rate, key-fact recall |
| **Classify / Score** | LLM | cols → label/score column | per-class P/R/F1; weighted agreement / MAE for ordinal; P@k / NDCG for ranking |
| **Match & Verify** | agent | company in row → typed link status | match accuracy, wrong-entity rate, explanation/source completeness |
| **Aggregate / Fold** | func | list-in-cell **or** rows grouped by key col → scalar (sum / count / avg / min / max) per group | correctness vs manual tally; group-completeness |
| **Compare / Diff** | func / LLM | 2+ cols → match / mismatch / delta + typed status (func for exact/numeric, LLM for semantic) | agreement with human; false-match rate |
| **Custom Prompt** *(Stretch)* | LLM | cols → column | per-use rubric |

**Row-producing** (emit rows, not cells — a produced row with no parent input cells is a *generated* row, §16 #7):

| Recipe | exec | Input → Output | Eval metric |
|--------|------|----------------|-------------|
| **Connector: Prozorro** | func | search params → rows (tender packages); winner = `award.status='active' → suppliers[].identifier.id` (EDRPOU) + `award.value` (§6a) | success rate, stable-ID completeness, provenance |
| **Manual upload** | func | file → normalized row (docling parse; other formats native, OCR only if no text layer, §7) | ingest success, OCR status |
| **Generate / Seed rows** | agent | prompt/params (+ optional seed col) → **new rows**, first col filled, `origin='generated'` | list precision/recall, dup rate, hallucinated-entity rate |

**Cross-row** (→ `cross_row_result`, not a grid column, §8):

| Recipe | exec | Input → Output | Eval metric |
|--------|------|----------------|-------------|
| **Cross-row connect** | func→agent | explicit row/col set → signal + evidence | pair precision/recall, false-positive rate |

**Engine feature (not a recipe) — Dead-end lock:** when a cell reaches a **terminal-empty** status (`NotFound` / `InsufficientData` / `SourceUnavailable`), downstream cells whose *required* inputs are all terminal-empty are auto-set `InsufficientData` and **never enqueued** — the empty result is **negative-cached** on `cache_key` so identical inputs don't re-hit a paid external provider. Only force-refresh (§4 step 6) overrides. Non-empty terminals (`ConflictingEvidence` / `Error` / `NeedsReview`, and `Answered`) do **not** propagate a lock. This is the cost-safety complement to the wavefront gate (§4 step 5): the wavefront decides *when inputs are ready*, dead-end lock decides *when a ready-but-empty input means "don't bother spending."*

**Deferred:**
- **Merge** (func→agent, one column/explicit row set → canonical row + merged-to links, eval: wrong-merge rate / missed-duplicate rate) — same shape as Cross-row connect, deferred to keep P0 to additive signals only; row-lifecycle mutation (canonical pick + `merged_into_row_id`) waits until Cross-row connect is proven.
- **Recursive / Expand walk** (agent, bounded depth) — follow chains (owner → owner's owner, beneficiary drill-down). New depth-iteration pattern; deferred to keep P0 recipes single-pass (rough-outline §5: "one pass").
- **Fixed row-class system** — a base taxonomy of row types for law-focused sheets (§16 #8). P0 rows are untyped; run-subset is manual queue selection only.

Language: UI English, switch to Ukrainian. Originals + citations stay in source language. AI output in the selected UI language. Translation is its own recipe that keeps a link to the original.

---

## 6a. Connector API map (pilot connectors)

Verified against live API docs (week-1 spike still confirms license/quota).

**Prozorro** — public, no auth for read. `func` connector, no LLM on clean structured parts (§7 hybrid).

| Need | Endpoint / path |
|---|---|
| Row feed | `GET /tenders` — sorted by `dateModified`, batch 100 (`limit`), cursor `next_page.offset`; sync-by-modification-date, poll ~5 min |
| Full tender | `GET /tenders/{id}` |
| Docs | `GET /tenders/{id}/documents` → `url`, `documentType`, `format`, `datePublished` (feeds upload/OCR/Extract) |
| Winner (deterministic) | `award.status == 'active'` → `award.suppliers[].identifier.id` = **EDRPOU** (+ `legalName`, `address`, `contactPoint`) |
| Amount | `award.value` = `{amount, currency}`; bid via `award.bid_id` |

→ **row = tender package**, tender grain (decision #3 — resolved §16). Winner EDRPOU + amount pulled with zero LLM.

**YouControl / YouScore** — REST JSON, API key (server-side only, §11), **per-module quota/license**.

| Module | Path / note |
|---|---|
| Registry (USR) | `/v1/usr/{EDRPOU}` — legal entity, founders, directors, address, KVED, status |
| Metered add-ons (separate license each) | sanctions/PEP, court cases, tax debt, beneficiaries, corporate-group affiliation, due-diligence score |

Key = EDRPOU. **Having a key ≠ having all modules** (§11) — week-1 spike verifies which modules the license grants + quota before recipes assume them.

Docs: [Prozorro tenders](https://prozorro-api-docs.readthedocs.io/en/master/tendering/basic-actions/tenders.html) · [Prozorro award](https://prozorro-api-docs.readthedocs.io/en/master/standard/award.html) · [YouScore endpoints](https://youscore.com.ua/en/faq/detailed-information-on-endpoints/) · [YouScore swagger](https://api.youscore.com.ua/swagger/index.html)

---

## 7. Document processing — three distinct modes

Do **not** call all of this "RAG." Three different problems:

| Mode | Question | Technique | Failure mode to avoid |
|------|----------|-----------|-----------------------|
| **Retrieve** (RAG) | "what does the doc say about Y?" | embed query → top-k chunks | — (this is Q&A → largely **Deferred**) |
| **Enumerate** | "list **all** mentions of X" | **map-reduce sweep over every chunk** | top-k silently under-counts; recall failure |
| **Structured Extract** | "pull fields into a schema" | hybrid (deterministic ingest + lazy LLM) | eager full-JSON extraction (see below) |

**Enumerate — the important one:**
```
if doc fits context:  single-shot on whole doc  ("list all X, quote + page each")
else:                 MAP each chunk → extract candidates
                      REDUCE → dedup / entity-resolve → cite
```
Every chunk is visited → full recall. 10 pages fits context → single-shot. 300-page court file → sweep. Eval **recall**, not just precision — the miss is the failure.

The Enumerate cell value is a **list** (§16 list-in-cell), so its citation is **per item, not per cell**: `citation_jsonb` is an array aligned to `value_jsonb` (§2), each entry anchoring one enumerated item back to the chunk/page it came from. After REDUCE/dedup, an item merged from several chunks carries all its supporting locators.

**Extraction strategy — hybrid, lazy default (not eager full-JSON):**
- **Ingest time, deterministic, cheap:** API connectors are already structured (Prozorro/YouControl) → store known fields as `jsonb`, no LLM.
- **On demand, LLM, lazy:** unstructured text or a new user-requested tag → run an extraction recipe → new column.
- Reject the "extract everything into one predetermined JSON upfront" idea: schemas differ wildly across doc types, it extracts things nobody asked for, and it fights the composable/user-driven model. Also **no separate document DB** — `jsonb` + `pgvector` in Postgres, keep lineage intact.

---

## 8. Agentic — bounded, in P0

Agentic **is** P0. The line is **bounded vs unbounded**, not agentic vs not.

| | P0 (allowed) | Deferred |
|---|---|---|
| scope | fixed input set (one row, or *explicitly selected* rows/cols) | roams everything itself |
| control | human picks the operation + inputs | agent plans + auto-runs steps |
| output | typed, cited, logged, eval'd | freeform synthesis |

**In P0:**
- **Web Search** — tool loop, row-scoped.
- **Match & Verify** — agent loop, row-scoped, fixed tool (YouControl): strategy → call → compare → typed status + evidence.
- **Cross-row connect** — *explicit* operation. User declares the row/column set. Two phases:

```
PHASE 1  CANDIDATE GEN (deterministic, no LLM):
  index rows by shared attributes (phone / email / address / EDRPOU /
  director / owner). Blocking: only pairs sharing a key become candidates.
  Cuts N² down to a handful.

PHASE 2  VERIFY (agentic, per candidate pair):
  agent compares the pair, explores YouControl/web to confirm/deny
  → typed status + per-signal citations.
```
Deterministic narrows; agent judges. Never agent-scans-everything (breaks isolation, blows context, kills citations). Every claimed connection cites the shared attribute **and both source records** — no naked assertions.

Each verified signal writes a **`cross_row_result`** row (§2), *not* a cell in the grid — a pairwise result has no single-row home, and keeping it out of `cell(row_id, column_id)` is what preserves the per-row isolation invariant (§3) for normal recipes. It records its input row/column versions; if an input column is rerun, the signal flags `is_stale` and waits for a user-confirmed re-verify (same "never auto-rerun" rule as §4).

**Deferred:** Assistant Plan/Auto (plans the whole investigation, auto-executes multi-step). Trust the core first, autonomy later.
- **Merge** — same shape as Cross-row connect (explicit, user-declared row set, deterministic-candidate → agent-verify), but the outcome changes row lifecycle instead of just adding a signal column: for each confirmed duplicate pair, one row is picked canonical, the other gets `merged_into_row_id` set + `state='merged'` (§5). **User confirms before merge commits** — same Preview gate as any other run (§4 step 4), because unlike a signal column this is not trivially undoable without an explicit unlock. Losing row's existing cells are untouched, just excluded from future enqueue batches (§4 step 5). Schema (`row.state`, `merged_into_row_id`) stays in place now so Cross-row connect's candidate-gen logic is reusable later — only the commit action is deferred.

Every agentic step: one bounded scope, logged, same eval as any recipe.

---

## 9. Provenance / citations

Principle 2 — every claim has an address.

- Store per emitted item: source locator (API field path / URL / page + char offset / timecode) in `citation_jsonb` — an **array** aligned to `value_jsonb` (§2), so list-in-cell / Enumerate results cite each item, not the cell as a whole.
- **Quote → locate anchoring:** model returns a verbatim quote; code string-searches it back in the source to get the offset. **Never trust model-reported page numbers** — verify the quote exists before storing.
- **Anchor in the source language, always.** The quote is captured in the source language even when the cell value is translated or summarized into the UI language (brief §10: originals + citations stay in source language). Translating the value must not break `locate()` — the quote searched is the original-language string, not the AI output.
- **OCR is noisy → fuzzy locate.** For OCR'd docs an exact string match will fail. Normalize (lowercase, collapse whitespace, strip punctuation) then token-window / edit-distance match; store the best offset **plus a `match_confidence`**. Below threshold → don't store a guessed offset; set the cell `NeedsReview`. A wrong-but-confident locator is worse than an honest "couldn't anchor."
- **Ingest via docling, not raw pytesseract.** Docling wraps Tesseract (ukr+rus+eng traineddata kept, §15) as its OCR backend but checks for a text layer first — OCR runs only on pages that actually lack one — and parses PDF/DOCX/XLSX/PPTX/HTML natively (raw pytesseract handles images only; owner brief P0 upload path needs docx/xlsx too). Docling also returns per-element **page + bbox**, a stronger citation locator than char-offset alone on scanned pages.
- Web results store at minimum: URL, title, fetched-at, supporting snippet.
- Chunks stay a technical layer, surfaced only via citation / verification view.

---

## 10. Models / OpenRouter (owner brief §9)

- Model + allowed provider endpoint configured by owner/admin **per recipe** — not a user-facing model switcher for Oksana.
- Per run, log: `model_id`, actual provider endpoint, recipe version, prompt hash (exact model revision if the provider exposes it).
- **Pin models to concrete IDs** — no floating `auto`/`latest`.
- Fallback **off by default**; if needed, only a pre-validated model+provider combo that passed the same eval. **Fallback-produced cells are not cached** (`run.used_fallback=true` → `cache_key` left non-hittable): otherwise a later run with the primary model up would serve a fallback value mislabeled as the primary model's, corrupting provenance. Next run misses cache → primary runs.
- Changing the model in a critical recipe → re-run eval.
- Fast models for simple row tasks; stronger model only for harder synthesis. Exact counts/patterns → code.
- **Embedding models are pinned too.** The same "no floating model" discipline applies to embeddings: `chunk.embed_model_id` (§2) records which model produced each vector. Retrieval compares only same-model vectors; swapping the embedding model is a versioned re-embed, never a silent mixed-vector-space drift.
- Providers: allowlist, no data collection, Zero Data Retention where a compatible endpoint exists. No keys or full payloads in logs.

---

## 11. Security / access / secrets

- Case **private by default**; share only by explicit action. Roles: owner / editor / viewer (reviewer = Stretch).
- Pilot uses **public data only**. If a user accidentally uploads a non-public file, it must **not** be silently sent to an external provider. **Enforced in P0, not deferred:** every document carries `external_ok` (§2) — connector-sourced rows (Prozorro/YouControl API) are inherently public → `true`; manual uploads are `false` until the user explicitly attests the file is public. Any recipe that calls an external provider (LLM / web / YouControl) checks `external_ok` on **every** source document in `row_context` at dispatch; any un-attested source → the run is **blocked** with "needs public attestation," never silently sent. This is the enforcement point for the brief §10 rule; full per-case/per-row private mode stays deferred (tech-stack §3), but the hard rule is met now, not aspirationally.
- **Secrets server-side only.** YouControl key lives behind one controlled server endpoint with rate limits + logging (no secret in logs, client, or repo). Week 1: verify the API contract, fields, license rights, and quota of that specific access — having a key ≠ having all modules.
- **External calls are idempotent across retries.** A worker can crash after incurring a paid/quota'd external call but before writing the cell; Procrastinate then retries → a naive design double-charges YouControl quota. The server-side proxy keeps a short-TTL idempotency cache keyed `(recipe_version, row_id, column_id, call_args_hash)`; an identical retried call reuses the stored response instead of re-hitting the provider. TTL is minutes (crash-retry window), not a data cache.
- Cost cap + caching + Preview gate spend before any full run.

---

## 12. Eval (owner brief §8)

- For each P0 recipe: a small representative real set. Part for tuning/validation, part **frozen held-out** until one final Demo-Day run.
- Cell-level feedback: verdict (correct/partial/incorrect/cannot-judge) + relevance 0–3 + error type (wrong entity / missed evidence / unsupported claim / wrong classification / citation mismatch / incomplete / source problem / other) + optional correct value.
- Metrics are **per component** (§6 table) — 90% is not a universal target.
- LLM-judge may scale open-answer checks **only after** measuring its agreement with Oksana; versioned prompt, audited, never replaces deterministic metrics.
- **Ground truth is a single-human dependency — name a backup.** Acceptance rests on Oksana across weeks 3-6; if she's unavailable, gates 3/5 can't be met. Brief §8 already invites a second domain annotator "за можливості" — make that a *named* second judge for a slice of critical examples (also gives human-agreement numbers), and front-load Oksana's critical build sessions into weeks 1-3 rather than back-loading them.

---

## 13. Deferred (must not block the pilot)

Q&A / large text synthesis as a required layer · Assistant Plan/Auto · **Merge** (row-lifecycle mutation, §6/§8) · **Recursive/Expand walk** (bounded-depth owner/beneficiary chains, §6) · **fixed row-class taxonomy** for law-focused sheets (§16 #8) · nested cases / case-as-row · auto source refresh + diff · multimedia (image/audio/video) · handwriting OCR / bad photos · sensitive or unpublished material · CMS / monitoring / alerts / auto-publish · open source.

---

## 14. Build order (6 weeks, gates)

| Week | Goal | Gate |
|------|------|------|
| 1 | Product+tech vertical: pick company X, fix logical row + fields + failure states. Spike **Prozorro** (stable per-participant fetch — official API/feed, not fragile scraping) + **YouControl**. Grid skeleton (rows, cols, sort/filter, source view). One recipe through Preview→run→column→Result. First eval rubric + dependency register. | One real row completes the whole core loop, no manual data substitution. |
| 2 | Real volume + recipe engine: connectors build tens→hundreds of rows. Stabilize Web Search + column dependencies. Provenance, partial failures, retry/caching, versioned runs. | Web Search produces a verifiable column on a representative subset. |
| 3 | Three P0 recipes: add Summarize + Classify/Score. Recipes accept derived columns as inputs. Typed statuses, citation opening, feedback controls. dev/held-out split per recipe. | Oksana builds a ≥2-column sequence herself. |
| 4 | Useful tender analysis: deterministic comparisons find repeated companies/attributes/patterns. Explicit cross-row op emits a signal with evidence. Tune recipes on Oksana's marks. Result + Google Sheets export on full volume. | First Result is already useful in the pilot investigation. |
| 5 | Hardening + acceptance rehearsal: runs on dev/validation (held-out frozen). Fix citation mismatch / source errors / stale deps. Verify permissions, secrets, cost, recovery. Spare capacity → Custom Prompt first, then court/declaration sources. Full run without dev help. | Oksana does the core loop solo; critical recipes pass agreed eval thresholds. |
| 6 | Demo Day: freeze version. One final run on frozen held-out (no further tuning). Full real-case run, saved Result + export. Honest metrics, active hours, typical errors + limits. Backup dataset/run for external failure. Post-school decision. | End-to-end real case run stands on its own. |

---

## 15. Tech stack

| Layer | Pick |
|---|---|
| Database | Postgres (+ `pgvector`, `jsonb`) |
| Backend language | Python |
| Backend framework | FastAPI |
| Frontend | React + TypeScript, Vite |
| Grid UI | TanStack Table + virtual scroll |
| DB access | SQLAlchemy 2.0 (async) + raw SQL for CTEs |
| Job queue | Procrastinate (Postgres `SKIP LOCKED`-based) |
| Realtime transport | SSE |
| LLM access | openai SDK → OpenRouter |
| Doc parsing / OCR | **docling** (Tesseract backend for OCR, ukr+rus+eng) | multi-format (PDF/DOCX/XLSX/PPTX/HTML/img), text-layer check → OCR only pages that lack one, bbox-level locators feed §9 citation anchoring. Pin docling + model versions (§10 discipline). |
| File storage | Cloudflare R2 |
| Auth | fastapi-users |
| Hosting | Railway |
| Desktop wrap (future) | Tauri |

Full rationale + alternatives considered: `tech-stack-decision.md`.

**Unresolved (production, not pilot-blocking):** private mode / external-call gating for non-public data; local-vs-cloud deployment split. See `tech-stack-decision.md` §3.

---

## 16. Open decisions — resolved

1. **Doc ops P0 set — resolved:** Enumerate (sweep) + Structured Extract only. RAG retrieval (Q&A) stays out of P0 — consistent with §13, which already defers Q&A/large-text-synthesis as a required layer.
2. **Enumerate output shape — resolved:** list-in-cell for P0. Explode-to-child-rows rejected, not deferred as "TBD" — it breaks the recipe contract in §3 (N cols → M cols, not → rows) and structurally overlaps with "nested cases / case-as-row," already Deferred in §13. If a later recipe needs per-item verification (e.g. check each enumerated entity against YouControl), model it as an explicit user-triggered op over selected list items — same pattern as §8 Cross-row connect — not automatic row explosion.
3. **Logical row v0 — resolved (Day 1-2 lock; week-1 data-confirm).** Row = **one Prozorro tender package at tender grain** (one `tenderID`) — *not* per-award, per-lot, per-participant, per-document, or per-chunk. Participants, bids, lots, awards, and package documents attach to that single row: multi-valued facts as list-in-cell (§16 #2), documents via `document.row_id`. Rationale: (a) matches owner brief §6 recommended unit; (b) it is the journalist's mental unit ("a procurement") that sort/filter/score operate on; (c) per-award / per-participant rows would be *automatic row-explosion*, which §16 #2 rejects; (d) winner EDRPOU + `award.value` stay addressable per row — single-lot = scalar, multi-lot = list keyed by `award`/lot slot. Cross-row connect (§8) and Match & Verify (§6) stay row-scoped on the company key regardless of lot count. **Week-1 confirm on real company-X data:** if multi-lot tenders dominate and per-lot scoring is needed, promote winner/amount to **award-grain columns** (still one row per tender) — do **not** escalate to award-grain rows. This unblocks Track B's row shape (`row.provenance_jsonb` keyed by `tenderID`).
4. **First P0 recipe — resolved:** no fixed pick. Team (3-4 devs) builds the P0 recipe candidates in parallel; week 1 gate is satisfied by whichever completes Preview→run→column→Result first. Precondition: the recipe interface (§3) must be stable before parallel work starts, so implementers aren't blocked on shared plumbing.
5. **Queue — resolved:** **Procrastinate** (Postgres `LISTEN/NOTIFY` + `SKIP LOCKED`) is the single queue — not a hand-rolled `cell.status` poller (§4). At estimated ceiling (~200-300 rows × ~50 columns/case ≈ 10-15k cells/case) this is comfortably within range; Redis/Celery only on an order-of-magnitude jump. The real subtlety is **not** throughput but *ordering*: parallel workers need DAG readiness enforced in data (wavefront-gated enqueue, §4 step 5), because Procrastinate has no built-in dependency ordering. Frontend (TanStack virtual scroll) also comfortable at this row count; the frontend risk is update *rate*, handled by batched flushes + reconcile-on-reconnect (§4 step 7).
6. **Cross-row result home — resolved:** signals land in a dedicated `cross_row_result` table (§2/§8), outside the column DAG — a pairwise result has no single-row home, and this keeps the per-row isolation invariant (§3) intact. Merge (which mutates row lifecycle) stays Deferred; its schema (`row.state`, `merged_into_row_id`, `terminal_scope`, `Rejected`) sits dormant.
7. **Can a recipe create rows? — resolved: yes.** A **row-producing** recipe shape (§6) emits rows, alongside cell-producing and cross-row shapes — same `exec()`/`cite`/`eval` contract (§3). Connectors already produce rows; **Generate / Seed rows** (agent) does it from a prompt (e.g. "find top-10 Ukrainian universities → 10 rows"). A produced row with **no parent input cells** is a *generated* row: `origin='generated'` + `generated_by_run_id` (§2) so it's visibly distinct from connector/upload rows and its provenance traces to the run. **This does not reopen decision #2** — #2 rejects *automatic per-item explosion* of a list-in-cell into child rows (implicit, breaks the isolation model); row-producing recipes are *explicit, user-invoked* operations whose product **is** rows. Per-item verification of a list still follows the #2 rule (explicit op over selected items), not auto-explosion.
8. **Row class / tag — deferred:** P0 rows are **untyped**. "Run rows of same class" (rough workflows) is served in P0 by **manual queue selection** (user picks a subset → run selected). A **fixed row-class taxonomy** (base types for law-focused sheets, so "run all rows of type *company*" is a first-class filter) is **deferred** (§13) — build it once the untyped model shows the friction, not speculatively.
