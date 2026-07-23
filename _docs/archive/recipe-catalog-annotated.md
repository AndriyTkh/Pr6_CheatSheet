# CheatSheet — Recipe Catalog (P0)

**Status:** working draft (rev. 2 — engine-correctness pass) **⚠ EDIT: this copy = rev. 2 + Maryna's review notes, 21.07. All edits marked ⚠. Andriy applies and owns rev. 3.**

> **APPLIED — every ⚠ edit and both open decisions below are now integrated into `_docs/ARCHITECTURE.md` rev. 3.** That file is the contract; this one is the review record. Resolutions: `NotApplicable` added as 8th cell status (arch §5, §16 #9) · multi-valued results = **one typed list cell**, with an **expansion gate** that blocks any per-item recipe until the user expands, in one of two modes — `inline` or `new_table` (arch §2a, §16 #2) · pairs/companies live on **derived sheets**, `cross_row_result` narrowed to no-row-shape signals (arch §2a, §16 #10) · row grain = **tender lot** (arch §16 #3) · dead-end lock fires on **any required** input (arch §3, §6) · Structured Extract promoted + fully specced, Formula/Compute, Start router, Expand, Pair builder added (arch §6) · YouControl person-mode = fixed 2-step + 1-day endpoint timebox (arch §6b) · Score preset rubrics = editable param defaults (arch §3) · Generate/Seed rows off the critical path (arch §6) · UI Ukrainian-only, Translation recipe dropped (arch §6, §16 #11). Do not re-apply these edits.
**Scope:** summer pilot vertical slice (Prozorro + YouControl, procurement case — buyer/period set in case config)

CheatSheet is a columnar, lineage-tracked compute graph over rows: each column is the memoized output of a versioned operation ("recipe"), and every cell carries provenance and a typed status.

## Background needed to read this catalog

A **recipe** is a versioned function signature: `exec_type` (`func` deterministic, or `agent` tool-using LLM loop), `input` (N≥1 column refs), `params` (typed schema), `output` (typed schema, M≥1 columns), plus `cite` (how each value anchors to a source) and `eval` (which metrics apply). Every recipe shape below shares this same `exec()`/`cite`/`eval` contract.

**⚠ EDIT (add to Background): params may ship with editable presets per case type (e.g. Score rubric "procurement v0"). A preset is a param default, not a hardcode — journalist can edit or replace it before run. Preset content comes from the pilot journalist workflow session.**

A **cell** holds `value_jsonb` (may be a list) + a typed `status` enum, never a nullable string. P0 active statuses: `Answered · InsufficientData · NotFound · SourceUnavailable · ConflictingEvidence · Error · NeedsReview`. `NotFound` / `InsufficientData` / `SourceUnavailable` are the **terminal-empty** statuses referenced below.

**⚠ OPEN DECISION (owner: Andriy, before week 2): `NotApplicable` is used by the pair recipe (direct contract / one bidder) but is NOT in this enum. Either add it as the 8th status, or implement skip-with-reason. Do NOT silently map to InsufficientData — "nothing to check here" and "not enough data" must stay distinguishable for the journalist.**

Execution is DAG-ordered and **wavefront-gated**: a cell only enqueues once all its input cells are terminal. Each cell computes a `cache_key = hash(recipe_version + resolved_input_hashes + params + model_id + output_slot)`; identical inputs hit the cache instead of re-running (and, for paid external calls, instead of re-spending).

A **generated row** is a row produced by a row-producing recipe with no parent input cells — it's tagged `origin='generated'` + `generated_by_run_id` so it's visibly distinct from connector/upload rows, and its provenance traces back to the run that made it.

---

## Recipe catalog (P0)

Three shapes, one contract: **cell-producing** (N cols → M cols over existing rows), **row-producing** (emit new rows), **cross-row** (→ a dedicated `cross_row_result` table, no single-row home — pairwise results are kept out of the row/column grid to preserve per-row isolation). Same `exec()`/`cite`/`eval` metadata for all three.

**⚠ EDIT (architecture sync, decision owner: Andriy): pairs must be journalist-visible. Proposal: pair results live as a DERIVED SHEET (new tab, row = pair) that re-enters the core — same recipes, sorting, citations, export work on it. `cross_row_result` stays for non-pair one-off signals that have no row shape. See "One Core" diagram, section 4.**

**Cell-producing:**

**⚠ EDIT: Structured Extract moves to FIRST row of this table — most-used recipe in real workflow, must be specified first. Full spec below the table.**

| Recipe | exec | Input → Output | Eval metric |
|--------|------|----------------|-------------|
| **Structured Extract** ⚠ move to top | func + LLM | doc/fields → typed columns (deterministic from API; LLM only for unstructured fragments) | precision/recall/F1 on critical fields |
| **NEW → Formula / Compute** ⚠ | func | referenced cols → computed column (arithmetic / date diff / ratio, e.g. days between company registration and tender date) | correctness vs manual calc |
| **Connector: YouControl** | func | company key (EDRPOU) → registry fields **⚠ EDIT: add 2nd mode: person key → their companies (needed for owner's-companies column in pilot workflow). Fixed 2-step, NOT recursive walk. If API endpoint check takes >1 day → move that column to stretch, workflow survives without it** | success rate, match accuracy on human sample |
| **Web Search** | agent | query cols → external-context column | precision@k, authoritative-source share, dup/broken-link rate |
| **Summarize** | LLM | text col → short column | citation-entailment rate, unsupported-claim rate, key-fact recall |
| **Classify / Score** | LLM | cols → label/score column **⚠ EDIT: + editable preset rubric per case type (see Background note)** | per-class P/R/F1; weighted agreement / MAE for ordinal; P@k / NDCG for ranking |
| **Match & Verify** | agent | company in row → typed link status | match accuracy, wrong-entity rate, explanation/source completeness |
| **Aggregate / Fold** | func | list-in-cell **or** rows grouped by key col → scalar (sum / count / avg / min / max) per group | correctness vs manual tally; group-completeness |
| **Compare / Diff** | func / LLM | 2+ cols → match / mismatch / delta + typed status (func for exact/numeric, LLM for semantic) | agreement with human; false-match rate |
| **Custom Prompt** *(Stretch)* | LLM | cols → column | per-use rubric |

**⚠ NEW — Structured Extract full spec (paste-ready):**
- input: one or more @-referenced columns
- param: ONE question in free text ("what is the total contract amount?"); one question = one output column (batch of questions = batch of columns, still 1:1)
- param: output type — number / date / money / text / list / entity. Type is required: it makes the column sortable and Formula-compatible
- behavior on absence: answer not present in source → `NotFound` with zero citation. Never guess, never fill from world knowledge
- cite: every value anchors to the exact source locator

**Row-producing** (emit rows, not cells — a produced row with no parent input cells is a *generated* row, see Background above):

| Recipe | exec | Input → Output | Eval metric |
|--------|------|----------------|-------------|
| **NEW → Start** ⚠ | func + LLM router | two fields: question + new column name → router picks connector (Prozorro / web search / …) or asks for upload → rows | router accuracy (right connector picked), success rate |
| **Connector: Prozorro** | func | search params → rows (~~tender packages~~ **⚠ EDIT: tender LOTS — lot = row unit, fixed at kick-off**); winner = `award.status='active' → suppliers[].identifier.id` (EDRPOU) + `award.value` | success rate, stable-ID completeness, provenance |
| **Manual upload** | func | file → normalized row (+ OCR if no text layer) | ingest success, OCR status |
| **NEW → Unnest / Explode** ⚠ | func | list-in-cell (e.g. participants[]) → child rows, one per element, keyed to parent row (lot id), provenance chain participant → lot → tender → source | fan-out completeness, key integrity |
| **NEW → Pair builder** ⚠ | func | child rows grouped by lot key → pair rows (A+B, A+C, B+C per lot) + aggregation across lots (co-bid count, win split) → derived sheet | pair completeness vs manual, count correctness |
| **Generate / Seed rows** **⚠ EDIT: priority = after connectors; not on pilot critical path (competitors derive deterministically from Prozorro co-bids)** | agent | prompt/params (+ optional seed col) → **new rows**, first col filled, `origin='generated'` | list precision/recall, dup rate, hallucinated-entity rate |

**Cross-row** (→ `cross_row_result`, not a grid column):

| Recipe | exec | Input → Output | Eval metric |
|--------|------|----------------|-------------|
| **Cross-row connect** | func→agent | explicit row/col set → signal + evidence **⚠ EDIT: scope narrows to non-pair signals once Pair builder + derived sheet land (see architecture sync note above)** | pair precision/recall, false-positive rate |

**Engine feature (not a recipe) — Dead-end lock:** when a cell reaches a **terminal-empty** status (`NotFound` / `InsufficientData` / `SourceUnavailable`), downstream cells whose *required* inputs are all terminal-empty are auto-set `InsufficientData` and **never enqueued** — the empty result is **negative-cached** on `cache_key` so identical inputs don't re-hit a paid external provider. Only force-refresh (an explicit cache-bust) overrides. Non-empty terminals (`ConflictingEvidence` / `Error` / `NeedsReview`, and `Answered`) do **not** propagate a lock. This is the cost-safety complement to the wavefront gate: the wavefront decides *when inputs are ready*, dead-end lock decides *when a ready-but-empty input means "don't bother spending."*

**⚠ EDIT (dead-end lock, close the gap): split inputs into required / optional. Lock must fire when ANY required input is terminal-empty (not only when ALL are) — a recipe with one missing required input is guaranteed InsufficientData, running it only burns the LLM call.**

**Deferred:**
- **Merge** (func→agent, one column/explicit row set → canonical row + merged-to links, eval: wrong-merge rate / missed-duplicate rate) — same shape as Cross-row connect, deferred to keep P0 to additive signals only; row-lifecycle mutation (canonical pick + `merged_into_row_id`) waits until Cross-row connect is proven.
- **Recursive / Expand walk** (agent, bounded depth) — follow chains (owner → owner's owner, beneficiary drill-down). New depth-iteration pattern; deferred to keep P0 recipes single-pass.
- **Fixed row-class system** — a base taxonomy of row types for law-focused sheets. P0 rows are untyped; run-subset is manual queue selection only.

~~Language: UI English, switch to Ukrainian. Originals + citations stay in source language. AI output in the selected UI language. Translation is its own recipe that keeps a link to the original.~~
**⚠ EDIT (Maryna's decision, 21.07): UI Ukrainian ONLY for the pilot — interface, recipes, AI output. English maybe post-demo as a separate layer. Translation recipe removed from P0 entirely. Unchanged: originals + citations always stay in source language.**
