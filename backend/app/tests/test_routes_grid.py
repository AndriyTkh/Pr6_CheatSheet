"""The grid API's two promises (§2a, §15).

1. **Every grid route scopes by `sheet_id`.** A case has ≥1 sheet, so a route
   that returns rows/columns/cells without naming a sheet is a one-grid-per-case
   assumption hardening into the interface. The structural half of this is
   asserted against the route table itself, so a *new* grid route added later
   without the scope fails here too — not just the eight that exist today. The
   behavioural half puts two sheets in one case and checks each route serves one
   and 404s the other.

2. **The OpenAPI JSON exports.** Role 5 generates TypeScript from it
   (`openapi-typescript`, tech-stack-decision.md "Shared FE/BE types"), so a
   spec that only renders in Swagger is not good enough — it has to serialize.
"""

import functools
import json
import uuid

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.main import app
from app.models import Case, Cell, Column, Row, Sheet
from app.models.enums import CellStatus, RowOrigin, SheetKind
from app.tests.conftest import requires_db

# Response models whose payload is grid data. A route returning any of these
# must be reachable only through a sheet.
GRID_PAYLOAD_NAMES = {"RowOut", "ColumnOut", "CellOut", "GridOut"}


def _model_names_in(node, components: dict, seen: set[str] | None = None) -> set[str]:
    """Every component schema name reachable from `node`, following `$ref`s.

    Recursive because the payload model is rarely the top-level one: a listing
    returns `Page_RowOut_`, whose `items` refs `RowOut`, and `GridOut` refs four
    of them. `seen` bounds the walk — component schemas can be mutually
    recursive, and the answer is a set either way.
    """
    if seen is None:
        seen = set()
    names: set[str] = set()
    if isinstance(node, dict):
        ref = node.get("$ref", "")
        if ref.startswith("#/components/schemas/"):
            name = ref.rsplit("/", 1)[-1]
            if name not in seen:
                seen.add(name)
                names.add(name)
                names |= _model_names_in(components.get(name, {}), components, seen)
        for key, value in node.items():
            if key != "$ref":
                names |= _model_names_in(value, components, seen)
    elif isinstance(node, list):
        for item in node:
            names |= _model_names_in(item, components, seen)
    return names


@functools.lru_cache(maxsize=1)
def _grid_operations() -> frozenset[tuple[str, str]]:
    """`(method, path)` for every operation whose 200 body carries grid data.

    Derived from the OpenAPI document rather than the route objects on purpose:
    the spec is the artifact Role 5 actually consumes, and since FastAPI 0.139
    `include_router` is lazy — `api_router.routes` holds `_IncludedRouter`
    wrappers with no `.path`, so reflecting over them tests nothing.
    """
    spec = app.openapi()
    components = spec.get("components", {}).get("schemas", {})
    return frozenset(
        (method, path)
        for path, operations in spec["paths"].items()
        for method, operation in operations.items()
        if _model_names_in(operation.get("responses", {}).get("200", {}), components)
        & GRID_PAYLOAD_NAMES
    )


# --------------------------------------------------------------------------
# 1a. Structural: the route table itself
# --------------------------------------------------------------------------


def test_there_are_grid_routes_to_check():
    """Guard against the scoping assertions passing vacuously."""
    assert len(_grid_operations()) >= 6


def test_every_grid_route_takes_sheet_id_in_its_path():
    offenders = sorted(p for _, p in _grid_operations() if "{sheet_id}" not in p)
    assert offenders == [], (
        f"grid route(s) not scoped to a sheet: {offenders} — a case has ≥1 sheet (§2a)"
    )


def test_no_route_returns_grid_data_from_a_case_path():
    """`/cases/{case_id}/rows` and its relatives must not exist.

    A case-level rows/columns/cells route is the exact shape of the assumption
    this task exists to prevent: it can only answer by picking a sheet for you.
    """
    offenders = sorted(p for _, p in _grid_operations() if "{case_id}" in p)
    assert offenders == [], f"case-scoped grid route(s): {offenders}"


def test_row_and_column_and_cell_have_no_unscoped_top_level_route():
    """No `/rows/{row_id}`-style escape hatch around the sheet scope."""
    unscoped = {"/rows/{row_id}", "/columns/{column_id}", "/cells/{row_id}/{column_id}"}
    assert unscoped & set(app.openapi()["paths"]) == set()


def test_every_row_out_field_exists_on_the_row_model():
    """The wire shape mirrors the locked schema — no invented fields (CLAUDE.md §5)."""
    from app.schemas import CellOut, ColumnOut, RowOut

    for schema, model in ((RowOut, Row), (ColumnOut, Column), (CellOut, Cell)):
        missing = [f for f in schema.model_fields if not hasattr(model, f)]
        assert missing == [], f"{schema.__name__} invents field(s) {missing}"


# --------------------------------------------------------------------------
# 2. OpenAPI export
# --------------------------------------------------------------------------


def test_openapi_json_exports_without_error():
    """`app.openapi()` must both build and serialize — the FE reads the JSON."""
    spec = app.openapi()
    dumped = json.dumps(spec)
    assert json.loads(dumped)["openapi"].startswith("3.")
    assert spec["info"]["title"] == "CheatSheet"


def test_openapi_covers_every_grid_entity():
    schemas = app.openapi()["components"]["schemas"]
    for name in ("SheetOut", "RowOut", "ColumnOut", "CellOut", "GridOut", "CaseOut"):
        assert name in schemas, f"{name} missing from the OpenAPI components"
    # Generic pages are what the listings return; they must be named, not inlined.
    assert any(n.startswith("Page_") for n in schemas)


def test_operation_ids_are_unique_and_readable():
    """`openapi-typescript` keys its output on operationId — duplicates collide."""
    operations = [
        op["operationId"]
        for path in app.openapi()["paths"].values()
        for op in path.values()
        if "operationId" in op
    ]
    assert len(operations) == len(set(operations)), "duplicate operationId"
    assert "list_rows" in operations
    assert "get_grid" in operations


def test_openapi_documents_the_sheet_scope_on_grid_paths():
    paths = app.openapi()["paths"]
    for path in ("/sheets/{sheet_id}/rows", "/sheets/{sheet_id}/columns"):
        params = paths[path]["get"]["parameters"]
        assert any(p["name"] == "sheet_id" and p["in"] == "path" for p in params)


# --------------------------------------------------------------------------
# 1b. Behavioural: two sheets in one case, over a real database
# --------------------------------------------------------------------------


@pytest.fixture
def client(session: AsyncSession) -> httpx.AsyncClient:
    """The app, talking to the test session — so the fixture's rollback still wins."""

    async def override_get_db():
        yield session

    app.dependency_overrides[get_db] = override_get_db
    transport = httpx.ASGITransport(app=app)
    yield httpx.AsyncClient(transport=transport, base_url="http://test")
    app.dependency_overrides.clear()


@pytest.fixture
async def two_sheets(session: AsyncSession) -> dict:
    """One case, two sheets, each with its own row, column and cell.

    The second sheet is what makes the scoping assertions mean something: every
    route must serve sheet A's data and refuse sheet B's under sheet A's id.
    """
    case = Case(name="scoping case", owner_id=uuid.uuid4())
    session.add(case)
    await session.flush()

    built = {"case": case}
    # b is `derived`, so it must name its parent sheet — `sheet_parent_iff_derived`
    # in 0002 records the sheet boundary the DAG crosses (§2a).
    for key, kind, grain in (
        ("a", SheetKind.source, "lot"),
        ("b", SheetKind.derived, "company"),
    ):
        sheet = Sheet(
            case_id=case.id,
            name=f"sheet {key}",
            kind=kind,
            grain_label=grain,
            parent_sheet_id=built["a"]["sheet"].id if kind is SheetKind.derived else None,
        )
        session.add(sheet)
        await session.flush()
        row = Row(
            case_id=case.id,
            sheet_id=sheet.id,
            origin=RowOrigin.connector,
            provenance_jsonb={"tenderID": f"T-{key}", "lotID": f"L-{key}"},
        )
        column = Column(
            case_id=case.id, sheet_id=sheet.id, name=f"@col-{key}", value_type="text"
        )
        session.add_all([row, column])
        await session.flush()
        cell = Cell(
            row_id=row.id,
            column_id=column.id,
            value_jsonb=f"value {key}",
            status=CellStatus.Answered,
        )
        session.add(cell)
        await session.flush()
        built[key] = {"sheet": sheet, "row": row, "column": column, "cell": cell}
    return built


@requires_db
async def test_case_lists_both_of_its_sheets(client, two_sheets):
    async with client as http:
        response = await http.get(f"/cases/{two_sheets['case'].id}/sheets")

    assert response.status_code == 200
    names = {s["name"] for s in response.json()}
    assert names == {"sheet a", "sheet b"}


@requires_db
async def test_rows_route_returns_only_its_own_sheets_rows(client, two_sheets):
    a, b = two_sheets["a"], two_sheets["b"]
    async with client as http:
        response = await http.get(f"/sheets/{a['sheet'].id}/rows")

    assert response.status_code == 200
    body = response.json()
    assert [r["id"] for r in body["items"]] == [str(a["row"].id)]
    assert str(b["row"].id) not in json.dumps(body)
    assert body["items"][0]["sheet_id"] == str(a["sheet"].id)


@requires_db
async def test_columns_route_returns_only_its_own_sheets_columns(client, two_sheets):
    a, b = two_sheets["a"], two_sheets["b"]
    async with client as http:
        response = await http.get(f"/sheets/{a['sheet'].id}/columns")

    assert [c["id"] for c in response.json()["items"]] == [str(a["column"].id)]
    assert str(b["column"].id) not in response.text


@requires_db
async def test_cells_route_returns_only_its_own_sheets_cells(client, two_sheets):
    a = two_sheets["a"]
    async with client as http:
        response = await http.get(f"/sheets/{a['sheet'].id}/cells")

    values = [c["value_jsonb"] for c in response.json()["items"]]
    assert values == ["value a"]
    # sheet b's cell holds "value b" — it must not leak in under sheet a's id
    assert "value b" not in response.text


@requires_db
async def test_grid_payload_is_one_sheet_whole(client, two_sheets):
    a = two_sheets["a"]
    async with client as http:
        response = await http.get(f"/sheets/{a['sheet'].id}/grid")

    body = response.json()
    assert body["sheet"]["id"] == str(a["sheet"].id)
    assert [c["id"] for c in body["columns"]] == [str(a["column"].id)]
    assert [r["id"] for r in body["rows"]] == [str(a["row"].id)]
    assert [c["value_jsonb"] for c in body["cells"]] == ["value a"]
    # the resume point for the live stream (§4 step 7)
    assert body["as_of_version"] == a["cell"].version
    assert body["row_total"] == 1


@requires_db
async def test_a_row_from_another_sheet_is_404_not_served(client, two_sheets):
    """The row exists — it is simply not on this sheet. That must not be a 200."""
    a, b = two_sheets["a"], two_sheets["b"]
    async with client as http:
        same = await http.get(f"/sheets/{a['sheet'].id}/rows/{a['row'].id}")
        crossed = await http.get(f"/sheets/{a['sheet'].id}/rows/{b['row'].id}")

    assert same.status_code == 200
    assert crossed.status_code == 404


@requires_db
async def test_a_column_from_another_sheet_is_404_not_served(client, two_sheets):
    a, b = two_sheets["a"], two_sheets["b"]
    async with client as http:
        same = await http.get(f"/sheets/{a['sheet'].id}/columns/{a['column'].id}")
        crossed = await http.get(f"/sheets/{a['sheet'].id}/columns/{b['column'].id}")

    assert same.status_code == 200
    assert crossed.status_code == 404


@requires_db
async def test_a_cell_from_another_sheet_is_404_not_served(client, two_sheets):
    a, b = two_sheets["a"], two_sheets["b"]
    async with client as http:
        same = await http.get(
            f"/sheets/{a['sheet'].id}/cells/{a['row'].id}/{a['column'].id}"
        )
        crossed = await http.get(
            f"/sheets/{a['sheet'].id}/cells/{b['row'].id}/{b['column'].id}"
        )

    assert same.status_code == 200
    assert crossed.status_code == 404


@requires_db
async def test_unknown_sheet_is_404_everywhere(client, two_sheets):
    missing = uuid.uuid4()
    async with client as http:
        for path in ("rows", "columns", "cells", "grid"):
            response = await http.get(f"/sheets/{missing}/{path}")
            assert response.status_code == 404, path


@requires_db
async def test_depth_filter_separates_the_two_grains(client, session, two_sheets):
    """§2a — an inline-expanded sheet holds depth 0 and depth 1 side by side."""
    a = two_sheets["a"]
    child = Row(
        case_id=two_sheets["case"].id,
        sheet_id=a["sheet"].id,
        origin=RowOrigin.derived,
        provenance_jsonb={},
        parent_row_id=a["row"].id,
        depth=1,
        ordinal=0,
    )
    session.add(child)
    await session.flush()

    async with client as http:
        both = await http.get(f"/sheets/{a['sheet'].id}/rows")
        source_only = await http.get(f"/sheets/{a['sheet'].id}/rows?depth=0")
        children = await http.get(f"/sheets/{a['sheet'].id}/rows?depth=1")

    assert both.json()["total"] == 2
    assert [r["id"] for r in source_only.json()["items"]] == [str(a["row"].id)]
    assert [r["id"] for r in children.json()["items"]] == [str(child.id)]
