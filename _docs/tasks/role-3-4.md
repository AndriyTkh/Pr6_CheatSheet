# Role 3 & 4 — Data Science / Agentic developers (shared column)

> Part of `_docs/TASKS.md` (index: gates, people, tracking rules, cross-role notes). Read the index once, then work only in this file. Edit only the `Status` line of a task you own.

Two people, one list — split by whichever half fits each person better, but keep both halves moving in parallel since they share the recipe contract (`recipes/base.py`, owned by Role 2) and the same eval loop (§12). **Track A: document scans/extraction.** **Track B: agentic recipes.** Folder: `backend/app/documents/`, `backend/app/citations/`, `backend/app/agents/`, `backend/app/recipes/`. Each task is tagged `[Track A]` / `[Track B]` / `[either track]` so the two of you edit different `Status` lines — never the same one.

**Verify lines** run from `backend/` with the venv active. A recipe is not `REVIEW` until its `Verify` passes. Recipe tests must pin LLM output through a stub/recorded response — a test that hits a live provider isn't a verification, it's a bill.

### Week 1 (2026-07-22 – 2026-07-28)

- **Task [either track]: Recipe catalog stubs against the contract**
  - **Status:** `TODO`
  - **Target date:** `2026-07-23`
  - Description: Once Role 2 ships `recipes/base.py`, stub out the P0 recipe classes (§6 table — including **Expand**, **Pair builder**, **Formula/Compute**, **Start** which weren't previously tasked here) in `recipes/cell_producing/`, `recipes/row_producing/`, `recipes/cross_row/` so both people can build in parallel without stepping on each other. Pick and fully implement the recipe the team chose in the kickoff decision (Role 1 task) first — that's the week 1 gate.
  - Inputs: `recipes/base.py` (Role 2).
  - Deliverable: stubs exist; the chosen first recipe works end to end.
  - **Verify:** `pytest app/tests/test_recipe_registry.py -q` (add it: every §6 P0 recipe is registered and satisfies the `Recipe` contract — schemas present, `consumes` declared).
  - Depends on: Role 2's recipe contract.
  - Reference: §3, §6.

- **Task [Track A — docs]: docling ingest pipeline**
  - **Status:** `TODO`
  - **Target date:** `2026-07-24`
  - Description: `documents/` — wire docling for PDF/DOCX/XLSX/PPTX/HTML parsing, text-layer check before OCR, Tesseract backend (ukr+rus+eng traineddata) only on pages that actually lack a text layer. No raw pytesseract calls outside docling.
  - Inputs: sample files (Role 1, curated batch arrives week 2, but Prozorro connector docs can be a first source in week 1).
  - Deliverable: a manually-uploaded or Prozorro-sourced doc parses into normalized content + per-element page/bbox.
  - **Verify:** `pytest app/tests/test_docling_ingest.py -q` (add it: a text-layer PDF never triggers OCR; parsed elements carry page + bbox).
  - Depends on: Role 2's Prozorro connector for doc links, or Role 1's manual samples.
  - Reference: §7, §9, §15.

- **Task [Track A — priority]: Structured Extract — lazy/hybrid, full spec**
  - **Status:** `TODO`
  - **Target date:** `2026-07-25`
  - Description: ARCHITECTURE.md rev. 3 promotes this to the pilot-priority recipe (§6, §16 #4) — its interface must be stable before the rest of parallel recipe work leans on it, so build it early, not in week 3 as the original plan had it. Deterministic extraction from already-structured connector data (no LLM); LLM only for unstructured fragments, on-demand per §7's "hybrid, lazy default." One question = one output column, always 1:1; several answers for a row land as one typed **list** cell with per-item citations, never as extra rows (§2a); absence → `NotFound` + zero citations, never a guess.
  - Inputs: docling pipeline; connector data; recipe contract.
  - Deliverable: working recipe, both the deterministic and LLM-lazy paths, list-output case included — likely candidate to satisfy the week 1 gate.
  - **Verify:** `pytest app/tests/test_structured_extract.py -q` (add it: structured input takes the no-LLM path — provider spy sees zero calls; multi-answer yields one list cell with per-item citations; absence yields `NotFound` with zero citations).
  - Depends on: docling + connectors + recipe contract.
  - Reference: §6 "Structured Extract — full spec", §7, §2a.

- **Task [Track B — agentic]: Web Search recipe skeleton**
  - **Status:** `TODO`
  - **Target date:** `2026-07-24`
  - Description: Tool-using loop, row-scoped: build query from selected columns, call search tool, select relevant results, explain the choice. Output schema per §3 (JSON-schema enforced).
  - Inputs: recipe contract; OpenRouter access (dependency register, Role 1).
  - Deliverable: a stub that runs and returns a typed, cited result on one row.
  - **Verify:** `pytest app/tests/test_web_search.py -q` (add it: stubbed search tool; output validates against the recipe's `output_schema`; the loop never reads outside `row_context`).
  - Depends on: Role 2's recipe contract + OpenRouter key.
  - Reference: §6, §8.

- **Task [Track B]: Start router recipe**
  - **Status:** `TODO`
  - **Target date:** `2026-07-26`
  - Description: Row-producing recipe (§6) — journalist's question + new column name → func+LLM router proposes a connector (Prozorro / web search / …) or asks for an upload. **The journalist approves before any run** (§4 step 4 Preview gate) — the router proposes, it never auto-executes. Not on the critical path for the demo (Prozorro is hardcoded for the pilot case), but it's a P0 recipe in the catalog and cheap to land now alongside the other row-producing work.
  - Inputs: recipe contract.
  - Deliverable: router proposes a connector/upload path for a sample question, gated behind Preview confirm.
  - **Verify:** `pytest app/tests/test_start_router.py -q` (add it: router returns a proposal only — spy asserts zero connector executions without an explicit confirm).
  - Depends on: Role 2's recipe contract.
  - Reference: §6 "Start".

### Week 2 (2026-07-29 – 2026-08-04) — merges the original plan's weeks 2+3

- **Task [Track A]: Chunking + embeddings**
  - **Status:** `TODO`
  - **Target date:** `2026-07-29`
  - Description: Chunk parsed documents, embed with a pinned embedding model (`embed_model_id` recorded per chunk, §10 — never a floating model), store in `pgvector`.
  - Inputs: docling pipeline.
  - Deliverable: chunks + embeddings queryable.
  - **Verify:** `pytest app/tests/test_chunking.py -q` (add it: every stored chunk carries a non-null pinned `embed_model_id`; vector dimension matches the schema).
  - Depends on: docling task.
  - Reference: §7, §10.

- **Task [Track A]: Citation quote→locate anchoring**
  - **Status:** `TODO`
  - **Target date:** `2026-07-30`
  - Description: `citations/` — model/extraction returns a verbatim quote, code string-searches it back into the source for the offset. Never trust a model-reported page number. Add fuzzy locate (normalize + token-window/edit-distance) for OCR'd text, with `match_confidence`; below threshold → `NeedsReview`, don't store a guessed offset. `citation_jsonb` is an array aligned to `value_jsonb` — cover the list-cell case (Structured Extract's list output) now, not as a later patch.
  - Inputs: chunking task; docling per-element page/bbox.
  - Deliverable: citations resolve to a real, verifiable location for both clean-text and OCR'd docs, including per-item citations on list cells.
  - **Verify:** `pytest app/tests/test_citations.py -q` (add it: a model-reported page that disagrees with the located offset loses; below-threshold fuzzy match yields `NeedsReview` and no stored offset; list cell gets one citation per item).
  - Depends on: chunking + docling tasks.
  - Reference: §9, §2a.

- **Task [Track B]: Match & Verify recipe**
  - **Status:** `TODO`
  - **Target date:** `2026-07-31`
  - Description: Agent loop, row-scoped, fixed tool = YouControl: choose search strategy (EDRPOU → name → person) → call → compare to row data → typed status + explanation + sources. Declares `per_item` consumption (§6 table) — blocked on a list input until Expand runs.
  - Inputs: YouControl connector (Role 2).
  - Deliverable: working recipe on real rows.
  - **Verify:** `pytest app/tests/test_match_verify.py -q` (add it: mocked YouControl; `per_item` against a list column is rejected at edge-add, not at runtime).
  - Depends on: Role 2's YouControl connector.
  - Reference: §6, §8.

- **Task [Track B]: Stabilize Web Search into a verifiable column (week 2 gate, half)**
  - **Status:** `TODO`
  - **Target date:** `2026-08-01`
  - Description: This is half the week 2 gate — Web Search must produce a column Oksana/Role 1 can actually verify against citations on a representative subset of rows.
  - Inputs: Web Search skeleton (week 1); citation anchoring (Track A, ideally landed by now — coordinate).
  - Deliverable: gate met.
  - **Verify:** eval run on the representative subset — every non-empty cell carries a resolvable citation; report the citation-resolution rate to Role 1 with the gate claim.
  - Depends on: Track A's citation work landing in parallel.
  - Reference: §14 week 2 gate.

- **Task [either track]: Summarize recipe**
  - **Status:** `TODO`
  - **Target date:** `2026-08-02`
  - Description: LLM recipe, text column → short column, citation-entailment checked at eval time. Must accept a derived column as input (e.g. Web Search output) — confirm with Role 2's column-dependency work. Declares `whole_list` (§6 table) — a list input is read as context, not exploded.
  - Inputs: recipe contract; citation anchoring.
  - Deliverable: working recipe.
  - **Verify:** `pytest app/tests/test_summarize.py -q` (add it: a list input is consumed whole — no row explosion; a derived column is accepted as input).
  - Depends on: Role 2's derived-column-input support.
  - Reference: §6.

- **Task [either track]: Classify/Score recipe**
  - **Status:** `TODO`
  - **Target date:** `2026-08-03`
  - Description: LLM recipe against a transparent, editable rubric preset (Oksana-defined, per Role 1's rubric task, recorded in `column.params_jsonb` per §3 "presets"), typed label/score output.
  - Inputs: eval rubric (Role 1).
  - Deliverable: working recipe.
  - **Verify:** `pytest app/tests/test_classify_score.py -q` (add it: rubric round-trips through `column.params_jsonb`; out-of-range score rejected by schema enforcement, never stored).
  - Depends on: Role 1's rubric.
  - Reference: §6, §3.

- **Task [either track]: dev/held-out wiring per recipe**
  - **Status:** `TODO`
  - **Target date:** `2026-08-04`
  - Description: Make sure each recipe's eval path can run against the dev/held-out split Role 1 is curating this week.
  - Inputs: Role 1's split.
  - Deliverable: eval runnable per recipe.
  - **Verify:** `pytest app/tests/test_eval_harness.py -q` (add it: each registered recipe exposes a runnable `eval`; the harness refuses to run against the held-out split without an explicit flag).
  - Depends on: Role 1.
  - Reference: §12.

### Week 3 (2026-08-05 – 2026-08-11)

- **Task [either track]: Deterministic comparisons (Aggregate/Fold, Compare/Diff, Formula/Compute)**
  - **Status:** `TODO`
  - **Target date:** `2026-08-05`
  - Description: Code-based (not LLM) recipes finding repeated companies/attributes/patterns — exact counts and matches are code, per §3's "not everything is an LLM" rule. Includes **Formula/Compute** (arithmetic/date-diff/ratio over referenced columns — e.g. days between company registration and tender date; `length()`/`contains()`/index access on lists, arithmetic requires a *typed* list, untyped rejected at edge-add, §6 table), previously untasked here.
  - Inputs: real volume of rows.
  - Deliverable: working recipes surfacing repeated participants/attributes and computed columns.
  - **Verify:** `pytest app/tests/test_deterministic_recipes.py -q` (add it: provider spy sees zero LLM calls; arithmetic on an untyped list is rejected at edge-add).
  - Depends on: connector volume (Role 2).
  - Reference: §3, §6.

- **Task [Track A or either]: Expand recipe (application layer)**
  - **Status:** `TODO`
  - **Target date:** `2026-08-06`
  - Description: The recipe-side half of Expand (§2a, §6) — pairs with Role 2's backend task. Wire `mode` param (`inline`/`new_table`), `dedup_by`, and confirm output onto `recipes/row_producing/`. This is what unblocks `@participants` → Companies sheet for the Act 2 workflow.
  - Inputs: Role 2's Expand backend, recipe contract.
  - Deliverable: expanding `@participants` from a real tender produces Companies-sheet rows with correct dedup.
  - **Verify:** `pytest app/tests/test_expand_recipe.py -q` (add it: both modes reachable through the recipe params; `dedup_by` collapses duplicate identifiers while preserving every company-to-lot link).
  - Depends on: Role 2's Expand backend.
  - Reference: §2a, §6.

- **Task [Track B or either]: Pair builder recipe (application layer)**
  - **Status:** `TODO`
  - **Target date:** `2026-08-07`
  - Description: Recipe-side half of Pair builder (§2a, §6, §8) — pairs with Role 2's backend task. Aggregates co-bid count, win split, shared owner/address per pair; emits `NotApplicable` for lots with <2 bidders. Reuses the same deterministic blocking logic as Cross-row connect's Phase 1.
  - Inputs: Role 2's Pair builder backend, Expand recipe (Companies sheet must exist).
  - Deliverable: Pairs sheet populated with real co-bid/win-split/shared-attribute signals.
  - **Verify:** `pytest app/tests/test_pair_builder_recipe.py -q` (add it: co-bid counts aggregate across lots for the same pair; `NotApplicable` on a 1-bidder lot; blocking logic shared with Cross-row connect, not duplicated).
  - Depends on: Expand recipe, Role 2's Pair builder backend.
  - Reference: §2a, §6, §8.

- **Task [Track B]: Cross-row connect — narrowed scope**
  - **Status:** `TODO`
  - **Target date:** `2026-08-08`
  - Description: Two-phase — deterministic candidate-gen (block on shared phone/email/address/EDRPOU/director/owner to cut N² to a handful, shared code with Pair builder's Phase 1), then agentic verify per candidate pair (compare, explore YouControl/web, typed status + evidence citing the shared attribute *and* both source records). Rev. 3 **narrows** this recipe's scope: anything with a stable pair grain (repeated co-bidding, win split, shared owner/address) now belongs on the Pairs sheet instead — Cross-row connect stays for genuinely one-off, no-row-shape signals only. Writes to `cross_row_result`, not a grid cell.
  - Inputs: candidate attributes available on rows (connector data); Pair builder landing in parallel (defines what's now out of scope here).
  - Deliverable: signal generation on real row pairs limited to no-row-shape cases, with evidence.
  - **Verify:** `pytest app/tests/test_cross_row_connect.py -q` (add it: Phase 1 cuts an N² candidate set to the blocked subset; output lands in `cross_row_result`, never in a grid cell).
  - Depends on: sufficient row volume + registry data; Pair builder recipe (to know what NOT to duplicate here).
  - Reference: §8, §16 #10.

- **Task [either track]: Tune recipes on Oksana's marks**
  - **Status:** `TODO`
  - **Target date:** `2026-08-09`
  - Description: Use Role 1's curated pattern examples + Oksana's feedback pass to adjust prompts/rubrics on Classify/Score, Pair builder, and Cross-row connect.
  - Inputs: Role 1's pattern-example doc + feedback.
  - Deliverable: measurably improved eval numbers on the dev set.
  - **Verify:** eval-harness run on the **dev** split before/after, numbers recorded. Held-out untouched — if the harness reports a held-out run, the task fails.
  - Depends on: Role 1's week 3 tasks.
  - Reference: §12.

### Week 4 (2026-08-12 – 2026-08-18) — merges the original plan's weeks 5+6, ends on Demo Day

- **Task [either track]: Run against dev/validation only, fix errors found**
  - **Status:** `TODO`
  - **Target date:** `2026-08-12`
  - Description: Fix citation mismatches, source errors, stale-dependency bugs surfaced by hardening runs. Do not touch the frozen held-out set.
  - Inputs: frozen held-out boundary (Role 1).
  - Deliverable: error list closed out or triaged.
  - **Verify:** `pytest app/tests -q` green; each fixed error has a regression test named in the closeout list.
  - Depends on: Role 1's freeze.
  - Reference: [owner-brief §11].

- **Task [Stretch, if capacity allows]: Custom Prompt recipe**
  - **Status:** `TODO`
  - **Target date:** `2026-08-14`
  - Description: Only after the above is solid — free-form prompt as its own recipe, per-use rubric. If capacity runs out this week, this is exactly the kind of item that moves into the buffer (§14a) rather than being rushed.
  - Inputs: spare capacity.
  - Deliverable: working Stretch recipe.
  - **Verify:** `pytest app/tests/test_custom_prompt.py -q` (add it: free-form output still passes schema enforcement; row isolation holds).
  - Depends on: everything else this week being done first.
  - Reference: §6 "Custom Prompt (Stretch)"; [owner-brief §4 Stretch].

- **Task [either track]: Final frozen held-out run**
  - **Status:** `TODO`
  - **Target date:** `2026-08-17`
  - Description: One run, no further tuning, against the frozen held-out set. Report honest metrics — this feeds Role 1's Demo Day metrics package.
  - Inputs: frozen set; stable recipes.
  - Deliverable: final metrics per recipe.
  - **Verify:** one eval-harness run against the held-out split, on the tagged commit, metrics recorded as-is — no re-run after seeing the numbers.
  - Depends on: week 3 hardening + this week's error fixes.
  - Reference: §12, §14 week 4 gate.
