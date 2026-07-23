# CheatSheet — Recipe Catalog (P0)

**Status:** working draft (rev. 2 — engine-correctness pass)
**Scope:** summer pilot vertical slice (Prozorro + YouControl, company-X tender case)

CheatSheet is a columnar, lineage-tracked compute graph over rows: each column is the memoized output of a versioned operation ("recipe"), and every cell carries provenance and a typed status.

## Background needed to read this catalog

A **recipe** is a versioned function signature: `exec_type` (`func` deterministic, or `agent` tool-using LLM loop), `input` (N≥1 column refs), `params` (typed schema), `output` (typed schema, M≥1 columns), plus `cite` (how each value anchors to a source) and `eval` (which metrics apply). Every recipe shape below shares this same `exec()`/`cite`/`eval` contract.

A **cell** holds `value_jsonb` (may be a list) + a typed `status` enum, never a nullable string. P0 active statuses: `Answered · InsufficientData · NotFound · SourceUnavailable · ConflictingEvidence · Error · NeedsReview`. `NotFound` / `InsufficientData` / `SourceUnavailable` are the **terminal-empty** statuses referenced below.

Execution is DAG-ordered and **wavefront-gated**: a cell only enqueues once all its input cells are terminal. Each cell computes a `cache_key = hash(recipe_version + resolved_input_hashes + params + model_id + output_slot)`; identical inputs hit the cache instead of re-running (and, for paid external calls, instead of re-spending).

A **generated row** is a row produced by a row-producing recipe with no parent input cells — it's tagged `origin='generated'` + `generated_by_run_id` so it's visibly distinct from connector/upload rows, and its provenance traces back to the run that made it.

---

## Recipe catalog (P0)

Three shapes, one contract: **cell-producing** (N cols → M cols over existing rows), **row-producing** (emit new rows), **cross-row** (→ a dedicated `cross_row_result` table, no single-row home — pairwise results are kept out of the row/column grid to preserve per-row isolation). Same `exec()`/`cite`/`eval` metadata for all three.

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

**Row-producing** (emit rows, not cells — a produced row with no parent input cells is a *generated* row, see Background above):

| Recipe | exec | Input → Output | Eval metric |
|--------|------|----------------|-------------|
| **Connector: Prozorro** | func | search params → rows (tender packages); winner = `award.status='active' → suppliers[].identifier.id` (EDRPOU) + `award.value` | success rate, stable-ID completeness, provenance |
| **Manual upload** | func | file → normalized row (+ OCR if no text layer) | ingest success, OCR status |
| **Generate / Seed rows** | agent | prompt/params (+ optional seed col) → **new rows**, first col filled, `origin='generated'` | list precision/recall, dup rate, hallucinated-entity rate |

**Cross-row** (→ `cross_row_result`, not a grid column):

| Recipe | exec | Input → Output | Eval metric |
|--------|------|----------------|-------------|
| **Cross-row connect** | func→agent | explicit row/col set → signal + evidence | pair precision/recall, false-positive rate |

**Engine feature (not a recipe) — Dead-end lock:** when a cell reaches a **terminal-empty** status (`NotFound` / `InsufficientData` / `SourceUnavailable`), downstream cells whose *required* inputs are all terminal-empty are auto-set `InsufficientData` and **never enqueued** — the empty result is **negative-cached** on `cache_key` so identical inputs don't re-hit a paid external provider. Only force-refresh (an explicit cache-bust) overrides. Non-empty terminals (`ConflictingEvidence` / `Error` / `NeedsReview`, and `Answered`) do **not** propagate a lock. This is the cost-safety complement to the wavefront gate: the wavefront decides *when inputs are ready*, dead-end lock decides *when a ready-but-empty input means "don't bother spending."*

**Deferred:**
- **Merge** (func→agent, one column/explicit row set → canonical row + merged-to links, eval: wrong-merge rate / missed-duplicate rate) — same shape as Cross-row connect, deferred to keep P0 to additive signals only; row-lifecycle mutation (canonical pick + `merged_into_row_id`) waits until Cross-row connect is proven.
- **Recursive / Expand walk** (agent, bounded depth) — follow chains (owner → owner's owner, beneficiary drill-down). New depth-iteration pattern; deferred to keep P0 recipes single-pass.
- **Fixed row-class system** — a base taxonomy of row types for law-focused sheets. P0 rows are untyped; run-subset is manual queue selection only.

Language: UI English, switch to Ukrainian. Originals + citations stay in source language. AI output in the selected UI language. Translation is its own recipe that keeps a link to the original.
