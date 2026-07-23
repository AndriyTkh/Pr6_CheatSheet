# Handoff — `role-2/wk2-api-routes`

Task: **API routes for grid consumption — sheets included** (`_docs/tasks/role-2.md`, Week 2).
Read this instead of the diff — it is the whole HTTP surface plus the places the shape is still open.

All routes are read-only (`GET`). Writes are a later task; nothing here mutates.

---

## The one rule the surface is built on

**Every route that returns grid data (`RowOut`, `ColumnOut`, `CellOut`, `GridOut`) is reachable only through `/sheets/{sheet_id}/…`.**

A case has ≥1 sheet (§2a), so a route serving rows without naming a sheet can only answer by picking one for you — that is one-grid-per-case hardening into the interface. There is deliberately **no** `/cases/{case_id}/rows`, no `/rows/{row_id}`, no `/columns/{column_id}`, no `/cells/{row_id}/{column_id}`. If you need a row you need its sheet, always.

This is asserted structurally against `app.openapi()` in `backend/app/tests/test_routes_grid.py`, so a grid route added later without the scope fails the suite — not just the ones that exist today.

---

## Route table

`sheet_id`, `case_id`, `row_id`, `column_id`, `document_id`, `run_id`, `recipe_id` are UUIDs; `version` is an int.

### Cases and sheets — the entry point

| Method | Path | operationId | Returns |
|---|---|---|---|
| GET | `/cases` | `list_cases` | `Page[CaseOut]` |
| GET | `/cases/{case_id}` | `get_case` | `CaseOut` |
| GET | `/cases/{case_id}/sheets` | `list_sheets` | `list[SheetOut]` — unpaginated, tab order |
| GET | `/sheets/{sheet_id}` | `get_sheet` | `SheetOut` |

**Start here.** A case is a set of sheets; the client lists them, picks one, and addresses everything else under its id.

### The grid

| Method | Path | operationId | Returns |
|---|---|---|---|
| GET | `/sheets/{sheet_id}/grid` | `get_grid` | `GridOut` — sheet + columns + rows + cells in one payload |
| GET | `/sheets/{sheet_id}/rows` | `list_rows` | `Page[RowOut]` |
| GET | `/sheets/{sheet_id}/rows/{row_id}` | `get_row` | `RowOut` |
| GET | `/sheets/{sheet_id}/rows/{row_id}/links` | `list_row_links` | `list[RowLinkOut]` — §2a lineage, **both directions** |
| GET | `/sheets/{sheet_id}/rows/{row_id}/documents` | `list_row_documents` | `list[DocumentOut]` |
| GET | `/sheets/{sheet_id}/columns` | `list_columns` | `Page[ColumnOut]` |
| GET | `/sheets/{sheet_id}/columns/{column_id}` | `get_column` | `ColumnOut` |
| GET | `/sheets/{sheet_id}/columns/{column_id}/inputs` | `list_column_inputs` | `list[ColumnInputOut]` — the DAG edges feeding it |
| GET | `/sheets/{sheet_id}/cells` | `list_cells` | `Page[CellOut]`, ordered by `version` |
| GET | `/sheets/{sheet_id}/cells/{row_id}/{column_id}` | `get_cell` | `CellOut` |

`GET /sheets/{sheet_id}/grid` is the one to paint with. Three round trips is three chances to hold a half-loaded sheet; `GridOut` is all three at one `sheet_id` and one `as_of_version`.

### Catalog and provenance

| Method | Path | operationId | Returns |
|---|---|---|---|
| GET | `/recipes` | `list_recipes` | `Page[RecipeOut]` — every `(id, version)`, not collapsed to a latest |
| GET | `/recipes/{recipe_id}/versions/{version}` | `get_recipe_version` | `RecipeOut` |
| GET | `/sheets/{sheet_id}/runs` | `list_sheet_runs` | `Page[RunOut]` — runs that filled cells on this sheet |
| GET | `/runs/{run_id}` | `get_run` | `RunOut` (§10: `model_id`, `cost_usd`, `used_fallback`, …) |
| GET | `/cases/{case_id}/documents` | `list_case_documents` | `list[DocumentOut]` |
| GET | `/documents/{document_id}` | `get_document` | `DocumentOut` (carries `external_ok`, §11) |

Documents are **case**-scoped, not sheet-scoped, because `document` hangs off `case_id` (+ an optional `row_id`) and has no sheet of its own. The per-row listing lives under the row, under its sheet.

### Health

`GET /health` → `{str: str}`; `GET /health/ready` → object. Unchanged from week 1.

---

## Query parameters

- **Paging**, on every `Page[T]` route and on `/grid`: `limit` (1–1000, default 100), `offset` (≥0, default 0). `Page` returns `{items, total, limit, offset}` where `total` is the **unpaginated** count, so the grid can size its scrollbar without walking every page.
- **`?depth=`** on `/rows` and `/grid` (§2a): `0` = source rows, `1` = inline-expanded children. Omit it and you get both grains interleaved, which is what an inline-expanded sheet actually is. **A grid that renders without honouring `depth` will show two grains as one flat table.**
- **`?target_depth=`** on `/columns`: only the columns that run on that grain.

On `/grid`, paging applies to **rows only** — columns are unpaginated (a sheet has tens, not thousands), and cells are fetched for the whole sheet rather than the returned row page. Pilot scale is ~10–15k cells per case; slicing them per page would make the client reassemble what the server already knows. **If you paginate rows on `/grid`, expect cells for rows you did not receive.**

---

## Shapes worth knowing before you render

- **`GridOut.as_of_version`** — the highest `cell.version` in the payload, `0` when the sheet has no cells. This is the resume point for the live SSE stream (§4 step 7): reconnect with `?since=as_of_version` when that endpoint lands (not in this task).
- **`GridOut.cells` is sparse, and that is correct.** A cell exists only where `row.depth == column.target_depth` (§2a). A hole in an inline-expanded sheet means the column does not run on that grain. **Absent ≠ pending** — do not render a missing cell as a spinner.
- **`CellOut.value_jsonb` is untyped on the wire** (`Any | None`): a cell may hold a scalar or a typed list (§2a). The **column's** `value_type` / `item_type` is what says which. `[]` with status `Answered` means "we looked, there are none" — different from `NotFound`, different from `NotApplicable` (§5, eight terminals; never collapse them in the UI).
- **`CellOut.citation_jsonb` is a list aligned index-for-index** with a list value (§9). Item *i* has its own locator.
- **`RowOut`** carries `sheet_id`, `depth`, `parent_row_id`, `ordinal`, `position`, plus generated `tender_id` / `lot_id`. `state` and `merged_into_row_id` are on the wire but **dormant** — P0 rows are always `active` (§5). Don't build UI on them.
- **`RowLinkOut`** is the N-ary lineage graph; `row.parent_row_id` is the 1:1 tree edge. `list_row_links` returns links where the row is on **either** end, because the interesting question differs by sheet: on Companies you ask "which lots did this company bid on", on `@tenders` you ask "which companies came out of this lot".
- **`ColumnInputOut.input_column_id` may live on another sheet.** The DAG spans the sheet boundary (§2a), so only the *dependent* column is scoped by the path — the input is not guaranteed to be on this sheet, and a naive lookup in the current sheet's column list will miss it.

## 404 semantics

- Unknown `sheet_id` → 404 on every nested route, before any query runs (`resolve_sheet`).
- A row/column/cell that exists **on a different sheet** → **404, not 200**. The object exists; it is simply not here. Cells are checked through *both* ends — `row.sheet_id` and `column.sheet_id` — because invariant 2 (§2) says they agree and checking one end would serve a violation instead of surfacing it.
- `get_cell` 404 also covers the legal-but-empty case: an off-grain intersection has no cell at all. That is a fact about the grid, not a missing result.

---

## Generating types (Role 5)

`app.openapi()` both builds and serializes — asserted in the suite, because a spec that only renders in Swagger is not good enough.

`operationId` is the **handler's function name** (`list_rows`, `get_grid`, …), set via `generate_unique_id_function` in `backend/app/main.py`. FastAPI's default would emit `list_rows_sheets__sheet_id__rows_get`, and would rename a frontend symbol every time a path moves. Uniqueness is asserted. Generic pages appear as named components (`Page_RowOut_`), not inlined objects.

There is no committed `openapi.json` artifact yet — generate it from the running app or `app.openapi()`. Say if you'd rather have it checked in; it's a one-line script and a decision about who owns keeping it fresh.

---

## Uncertainties — flagging, not deciding

1. **`run` has no `case_id`, so "the runs of a case" is not a query the schema supports.** Exposed as `GET /sheets/{sheet_id}/runs` (joining through the cells the runs filled) + `GET /runs/{run_id}`. That is also the question the journalist actually asks ("what produced this grid"), so it may be the intended shape — but it may equally be a missing FK in `0001`. **Worth a team decision.** Widening it is a new numbered migration, not a route change (`CLAUDE.md` §5). Nothing was silently diverged: no `case_id` was invented.
2. **§15 names SSE as the realtime transport, and `cell.version` / `GridOut.as_of_version` are built for a `?since=` resume — but no SSE endpoint is in this task.** The read surface is shaped to accept one without changing; whoever adds it should not need to touch these routes.
3. **Whole-sheet cells on `/grid` is a pilot-scale bet** (~10–15k cells/case). If a case gets much larger, `/grid` is the first thing to feel it, and the fix is cells-for-the-returned-row-page — which changes the payload contract, so decide before Role 5 depends on the current one.
4. **No auth on any route.** `fastapi-users` is the §15 pick and `case.is_private` defaults true (§11), but nothing here filters by `owner_id` or `case_member`. **Every case is currently visible to every caller.** That is a separate task; do not ship this surface publicly as-is.
5. **`SheetOut.grain_label` is a free string** (`lot` / `company` / `pair` / `document` per §2a) rather than an enum — the migration does not constrain it, so the ORM does not either. The frontend should treat unknown values as displayable text, not switch exhaustively on it.

## Dead ends — don't redo these

- **Do not assert route shape by reflecting over `api_router.routes`.** On FastAPI 0.139 `include_router` is lazy: those entries are `_IncludedRouter` objects with no `.path` and no `.response_model`. The first version of the structural tests did exactly this and passed vacuously wherever it did not outright `AttributeError`. The tests now walk `app.openapi()` instead, which is also the artifact Role 5 consumes.
- **A `derived` sheet must have a `parent_sheet_id`** — `sheet_parent_iff_derived` in `0002`. Any fixture building a two-sheet case hits this immediately.

## Verify

```
cd backend
.venv/Scripts/Activate.ps1
CS_TEST_DATABASE_URL=postgresql+asyncpg://cheatsheet:cheatsheet@127.0.0.1:55432/cheatsheet pytest -q
```

At handoff: **106 passed, 0 skipped, 0 failed**; `test_routes_grid.py` alone 19 passed, 0 skipped (DB tests ran — they skip silently without the URL, and a skipped test is not a pass). `ruff check app` clean.

Note this branch shares a working tree with `role-2/wk2-queue`; the Procrastinate work (`app/tasks/`, `services/cell_execution.py`, `scripts/apply_queue_schema.py`, the `registry.catalog()` helper, the `pyproject.toml` deps) is deliberately **not** committed here and belongs to that branch.
