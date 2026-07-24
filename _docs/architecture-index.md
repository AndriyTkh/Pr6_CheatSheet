# ARCHITECTURE.md — section index

Read the sections your task cites, not the whole file. `ARCHITECTURE.md` is 568 lines; a typical task needs 30–60 of them.

**How to use:** `Read _docs/ARCHITECTURE.md offset=<start> limit=<end - start + 1>`. Humans: your editor's go-to-line.

**This file is a pointer, not a contract.** `ARCHITECTURE.md` itself is the contract — never quote a spec from here. Line numbers drift the moment anyone edits ARCHITECTURE.md, so:

- Whoever edits `ARCHITECTURE.md` regenerates this table in the same commit.
- Regenerate with: `rg -n '^## ' _docs/ARCHITECTURE.md` (ends = next start − 1; last section ends at EOF).
- If the line you land on doesn't match the section name below, the table is stale — regenerate it before trusting it, and don't work around it silently.

## Sections

| § | Section | Lines | Read it when |
|---|---------|-------|--------------|
| — | Title + rev. header | 1–10 | Checking which rev. the contract is at. |
| 0 | Core idea in one line | 11–18 | Onboarding; sanity-checking that a feature belongs in the pilot at all. |
| 1 | Components | 19–35 | Frontend grid work; anything asking "which layer owns this?" |
| 2 | Data model (Postgres) | 36–77 | ORM/models, any query, any migration question. Pairs with `migrations/0001`. |
| 2a | Lists, the expansion gate, and sheets | 78–141 | List cells, the `per_item` gate, Expand, sheets, grain/`target_depth`. The most-cited section in the task lists. |
| 2a | └ The list cell | 86–91 | `value_type='list'`, `item_type`, per-item citations. |
| 2a | └ The gate — where the block fires | 92–102 | Edge-add rejection rules and the message it must produce. |
| 2a | └ Expand — two modes, one recipe | 103–121 | `inline` vs `new_table`, `dedup_by`, `row_link`. |
| 2a | └ Sheets | 122–141 | Sheet boundaries, cross-sheet DAG, derived sheets. |
| 3 | Recipe format | 142–173 | Writing any recipe; `recipes/base.py`; schema enforcement; presets. |
| 4 | Execution + DAG | 174–218 | Cycle check, Preview gate, wavefront enqueue, `cache_key`, SSE, staleness. |
| 5 | Typed cell status | 219–247 | The eight statuses; what propagates as what; `NotApplicable` vs `InsufficientData`. |
| 6 | Recipe catalog (P0) | 248–330 | Which recipes exist, their `consumes` flags, per-recipe full specs. |
| 6b | Recipe scope guards | 331–339 | "Should this be one recipe or two?" — note it sits **before** §6a in the file. |
| 6a | Connector API map (pilot connectors) | 340–373 | Prozorro + YouControl endpoints, winner extraction, license/module caveats. |
| 7 | Document processing — three distinct modes | 374–401 | docling, OCR trigger rules, chunking, the hybrid/lazy extract default. |
| 8 | Agentic — bounded, in P0 | 402–446 | Agent loops, row isolation, candidate-gen blocking, Pair builder / Cross-row connect. |
| 9 | Provenance / citations | 447–460 | quote→locate anchoring, `citation_jsonb`, `match_confidence`. |
| 10 | Models / OpenRouter | 461–473 | Model pinning, `embed_model_id`, run logging. |
| 11 | Security / access / secrets | 474–483 | `external_ok`, server-side key proxy, idempotency, cost caps, permissions. |
| 12 | Eval | 484–495 | `cell_feedback`, rubric, dev/held-out split. |
| 13 | Deferred (must not block the pilot) | 496–501 | Before saying yes to scope. Nothing here gets a task. |
| 14 | Build order (4 weeks + buffer, gates) | 502–512 | Gate definitions the TASKS.md gate table is dated against. |
| 14a | Buffer — 2026-08-19 – 2026-08-28 | 513–521 | What the buffer may and may not be used for. |
| 15 | Tech stack | 522–546 | Picking a library; pairs with `tech-stack-decision.md` for the *why*. |
| 16 | Open decisions — resolved | 547–568 | A resolved decision you're about to re-litigate: #2 `row_link`, #3 lot grain, #4 Structured Extract priority, #9 non-`UA-EDR` → `NotApplicable`, #10 pair grain. |
