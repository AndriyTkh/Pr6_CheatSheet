# CheatSheet API

HTTP surface generated from `backend/app/api/routes/`. This doc is a human-readable
mirror of the OpenAPI spec FastAPI generates from that code — the code is the source
of truth (`operationId` = handler function name, see `backend/app/main.py`). Regenerate
this doc, don't hand-edit around a stale route.

Contract: `_docs/ARCHITECTURE.md` (`§N` refs below point there via
`_docs/architecture-index.md`).

---

## Conventions

- **Base path:** none — routes are mounted at root (`/health`, `/cases`, …).
- **Content type:** `application/json` for all requests/responses.
- **IDs:** UUIDv4 path params everywhere (`case_id`, `sheet_id`, `row_id`, `column_id`, `run_id`, `document_id`, `recipe_id`).
- **Auth:** not yet wired into the route layer (no `Depends(current_user)` on any route as of this doc).
- **Errors:** standard FastAPI `HTTPException` shape —
  ```json
  { "detail": "No case <uuid>" }
  ```
  except `EdgeRejected` (§4 step 2 — invalid column composition), which is caught
  globally and returned as **422** with a journalist-facing message:
  ```json
  { "detail": "<human message naming the column and the fix>", "reason": "EdgeRejected" }
  ```
- **Pagination:** every list route takes `limit` (1–1000, default 100) and `offset`
  (≥0, default 0) as query params, and returns:
  ```json
  { "items": [...], "total": <int>, "limit": <int>, "offset": <int> }
  ```
  `total` is the unpaginated count. Exceptions: `GET /cases/{case_id}/sheets` (a case
  has a handful of sheets, not thousands) and `GET /sheets/{sheet_id}/columns/{column_id}/inputs`
  return a bare list.
- **Scoping:** grid resources (rows, columns, cells, runs) are nested under
  `/sheets/{sheet_id}/…`. There is no unscoped `/rows/{row_id}` — a row is always
  addressed through the sheet it belongs to (§2a), on purpose.

---

## Health

| Method | Path | Summary |
|---|---|---|
| GET | `/health` | Liveness — no dependencies touched |
| GET | `/health/ready` | Readiness — DB reachable + migration 0002 applied |

`GET /health/ready` response:
```json
{
  "status": "ok",
  "database": "ok",
  "migration_0002_applied": true,
  "config": { "...": "masked (§11) — presence only, never a secret value" }
}
```

---

## Cases

`§2a`, `§11`. A case is the container a set of sheets hangs off.

| Method | Path | Summary |
|---|---|---|
| GET | `/cases` | List cases (paginated) → `Page[CaseOut]` |
| GET | `/cases/{case_id}` | Get one case → `CaseOut` |
| GET | `/cases/{case_id}/sheets` | List the case's sheets, tab order → `SheetOut[]` |

**CaseOut**

| Field | Type |
|---|---|
| `id` | uuid |
| `name` | string |
| `owner_id` | uuid |
| `is_private` | bool |
| `created_at` | datetime |

---

## Sheets

`§2a`. A case is a *set* of sheets — every grid route below is scoped to one.

| Method | Path | Summary |
|---|---|---|
| GET | `/sheets/{sheet_id}` | Get one sheet → `SheetOut` |
| GET | `/sheets/{sheet_id}/grid` | Columns + rows + cells in one payload → `GridOut` |

**SheetOut**

| Field | Type |
|---|---|
| `id` | uuid |
| `case_id` | uuid |
| `name` | string |
| `kind` | `SheetKind` enum |
| `grain_label` | string — `'lot' \| 'company' \| 'pair' \| 'document'` |
| `parent_sheet_id` | uuid \| null — set on derived sheets |
| `produced_by_run_id` | uuid \| null |
| `position` | int |
| `created_at` | datetime |

**`GET /sheets/{sheet_id}/grid`** — query: `limit`, `offset`, `depth` (0 = source
rows, 1 = expanded children). Rows are paginated; columns and cells are fetched for
the whole sheet (~10–15k cells/case at pilot scale). `cells` is sparse — a cell exists
only where `row.depth == column.target_depth` (§2a); absent ≠ pending.

**GridOut**

| Field | Type |
|---|---|
| `sheet` | `SheetOut` |
| `columns` | `ColumnOut[]` |
| `rows` | `RowOut[]` |
| `cells` | `CellOut[]` — sparse |
| `as_of_version` | int — highest `cell.version` in payload, 0 if none |
| `row_total` | int |
| `row_limit` | int |
| `row_offset` | int |

---

## Rows

`§2a`. Always addressed under a sheet — no unscoped `/rows/{row_id}`.

| Method | Path | Summary |
|---|---|---|
| GET | `/sheets/{sheet_id}/rows` | List rows (paginated; `depth` filter) → `Page[RowOut]` |
| GET | `/sheets/{sheet_id}/rows/{row_id}` | Get one row → `RowOut` |
| GET | `/sheets/{sheet_id}/rows/{row_id}/links` | Lineage links touching this row, both directions → `RowLinkOut[]` |
| GET | `/sheets/{sheet_id}/rows/{row_id}/documents` | Source documents attached to this row → `DocumentOut[]` |

**RowOut**

| Field | Type |
|---|---|
| `id` | uuid |
| `case_id` | uuid |
| `sheet_id` | uuid |
| `origin` | `RowOrigin` enum |
| `provenance_jsonb` | object |
| `generated_by_run_id` | uuid \| null |
| `state` | `RowState` enum |
| `merged_into_row_id` | uuid \| null |
| `parent_row_id` | uuid \| null — inline expansion (§2a) |
| `depth` | int — 0 = source grain, 1 = expanded child |
| `ordinal` | int \| null |
| `position` | int |
| `tender_id` | string \| null — lot grain, read-only |
| `lot_id` | string \| null — lot grain, read-only |
| `created_at` | datetime |

**RowLinkOut**

| Field | Type |
|---|---|
| `child_row_id` | uuid |
| `parent_row_id` | uuid |
| `relation` | `RowLinkRelation` enum |
| `source_cell_row_id` | uuid \| null |
| `source_cell_column_id` | uuid \| null |
| `source_ordinal` | int \| null — index into source cell's value/citation arrays (§9) |
| `created_at` | datetime |

---

## Columns

`§4`, `§2a`. The DAG nodes of one sheet.

| Method | Path | Summary |
|---|---|---|
| GET | `/sheets/{sheet_id}/columns` | List columns (paginated; `target_depth` filter) → `Page[ColumnOut]` |
| GET | `/sheets/{sheet_id}/columns/{column_id}` | Get one column → `ColumnOut` |
| GET | `/sheets/{sheet_id}/columns/{column_id}/inputs` | DAG edges feeding this column → `ColumnInputOut[]` |

**ColumnOut**

| Field | Type |
|---|---|
| `id` | uuid |
| `case_id` | uuid |
| `sheet_id` | uuid |
| `name` | string |
| `value_type` | string — `'list'` opts into §2a list rules |
| `item_type` | string \| null — only meaningful when `value_type='list'` |
| `recipe_id` | uuid \| null — null on source/seed columns |
| `recipe_version` | int \| null |
| `output_slot` | string |
| `params_jsonb` | object |
| `output_lang` | string \| null |
| `status` | `ColumnStatus` enum — rollup over this column's cells (§5), display only |
| `target_depth` | int — grain this column runs on (§2a) |
| `position` | int |
| `created_at` | datetime |

**ColumnInputOut** (one DAG edge — input column may live on a parent sheet, §2a)

| Field | Type |
|---|---|
| `column_id` | uuid |
| `input_column_id` | uuid |
| `is_required` | bool |
| `consumes` | `InputConsumption` enum — what the §2a expansion gate checks |

---

## Cells

`§4`, `§5`, `§9`. Row × column intersection, scoped through both ends to one sheet.

| Method | Path | Summary |
|---|---|---|
| GET | `/sheets/{sheet_id}/cells` | List a sheet's cells, ordered by `version` (paginated) → `Page[CellOut]` |
| GET | `/sheets/{sheet_id}/cells/{row_id}/{column_id}` | Get one cell → `CellOut` |

404 on the single-cell route also covers the legal-but-empty case: an off-grain
intersection (`row.depth != column.target_depth`) has no cell at all — that's a fact
about the grid, not a missing result.

**CellOut**

| Field | Type |
|---|---|
| `row_id` | uuid |
| `column_id` | uuid |
| `value_jsonb` | any \| null — scalar or JSON array; column's `value_type`/`item_type` says which |
| `status` | `CellStatus` enum (§5 — 8 typed statuses) |
| `citation_jsonb` | array — aligned index-for-index with a list value (§9) |
| `cache_key` | string \| null |
| `run_id` | uuid \| null |
| `version` | int — monotonic; backs reconnect catch-up (§4 step 7) |
| `updated_at` | datetime |

---

## Runs

`§10` — provenance log: what produced a value, at what cost, with which model.

| Method | Path | Summary |
|---|---|---|
| GET | `/sheets/{sheet_id}/runs` | Runs that produced cells on this sheet (paginated) → `Page[RunOut]` |
| GET | `/runs/{run_id}` | Get one run → `RunOut` |

No `/cases/{case_id}/runs` — `run` has no `case_id` column, so that's not a query the
schema supports; runs are reachable per sheet through the cells they filled.

**RunOut**

| Field | Type |
|---|---|
| `id` | uuid |
| `recipe_id` | uuid |
| `recipe_version` | int |
| `model_id` | string \| null — pinned concrete model id, never a floating alias |
| `provider_endpoint` | string \| null |
| `prompt_hash` | string \| null — no prompt text, no key |
| `params_jsonb` | object |
| `used_fallback` | bool |
| `cache_bust` | bool |
| `cost_usd` | decimal \| null |
| `status` | string |
| `created_at` | datetime |

---

## Recipes

`§3`. Global catalog, not case-scoped — what the "add column" picker reads.

| Method | Path | Summary |
|---|---|---|
| GET | `/recipes` | List recipe versions, newest first (paginated) → `Page[RecipeOut]` |
| GET | `/recipes/{recipe_id}/versions/{version}` | Get one pinned recipe version → `RecipeOut` |

Identity is `(id, version)` — a shipped version is never mutated; an existing column
stays pinned to the exact version that produced its results.

**RecipeOut**

| Field | Type |
|---|---|
| `id` | uuid |
| `version` | int |
| `name` | string |
| `exec_type` | `RecipeExecType` enum |
| `shape` | `RecipeShape` enum |
| `volatile` | bool |
| `params_schema` | object (JSON Schema) |
| `output_schema` | object (JSON Schema) — enforced server-side (backend/CLAUDE.md) |
| `cite_spec` | object |
| `eval_spec` | object |
| `created_at` | datetime |

---

## Documents

`§7`, `§9`, `§11`. Case-scoped, not sheet-scoped — a document hangs off `case_id`
(and optionally a `row_id`).

| Method | Path | Summary |
|---|---|---|
| GET | `/cases/{case_id}/documents` | List a case's source documents → `DocumentOut[]` |
| GET | `/documents/{document_id}` | Get one document → `DocumentOut` |

**DocumentOut**

| Field | Type |
|---|---|
| `id` | uuid |
| `case_id` | uuid |
| `row_id` | uuid \| null — package documents hang off their row (§6) |
| `url` | string \| null |
| `doc_type` | string \| null |
| `format` | string \| null |
| `storage_key` | string \| null |
| `has_text_layer` | bool \| null |
| `ocr_status` | string \| null — `null \| pending \| ok \| failed` |
| `source_lang` | string \| null |
| `external_ok` | bool — §11 hard gate; `false` blocks the document from any external provider |
| `created_at` | datetime |

---

## Not yet in the API (as of this doc)

Write/mutation routes (create case, add column, edit cell, trigger run, upload
document) aren't in `api/routes/` yet — everything above is read-only (`GET`). Update
this doc when those land.
