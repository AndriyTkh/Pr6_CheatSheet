"""The ORM must mirror `0001` + `0002` exactly — no drift, no invented fields.

These tests parse the migration SQL and diff it against the mapped tables, so a
model that grows a column the contract doesn't have fails here rather than at
the first query against a real database (CLAUDE.md §5).
"""

import re
from pathlib import Path

import pytest
from sqlalchemy.orm import configure_mappers

import app.models  # noqa: F401  — registers every mapper
from app.db.base import Base

MIGRATIONS = Path(__file__).resolve().parents[3] / "_docs" / "migrations"

#: tables the pilot's ORM layer maps (fastapi-users owns the user table, §15)
MAPPED_TABLES = {
    "case",
    "case_member",
    "recipe",
    "row",
    "column",
    "column_input",
    "run",
    "cell",
    "document",
    "chunk",
    "cross_row_result",
    "cell_feedback",
    "sheet",
    "row_link",
}


def _sql() -> str:
    """Both migrations, comments stripped — a `;` inside a comment ends nothing."""
    raw = "\n".join(
        (MIGRATIONS / name).read_text(encoding="utf-8")
        for name in ("0001_core_schema.sql", "0002_sheets_and_lot_grain.sql")
    )
    return "\n".join(line.split("--", 1)[0] for line in raw.splitlines())


def _columns_from_sql(table: str, sql: str) -> set[str]:
    """Column names for one table: its CREATE body plus every later ADD COLUMN."""
    body = re.search(
        rf'CREATE TABLE "?{table}"?\s*\((.*?)\n\);', sql, re.DOTALL | re.IGNORECASE
    )
    assert body, f"{table} not found in the migrations"

    names: set[str] = set()
    depth = 0
    for raw in body.group(1).splitlines():
        line = raw.strip()
        if not line:
            continue
        if depth == 0:
            match = re.match(r'"?([a-z_]+)"?\s+[a-z]', line, re.IGNORECASE)
            if match and not line.upper().startswith(
                ("PRIMARY KEY", "FOREIGN KEY", "REFERENCES", "CONSTRAINT", "CHECK", "UNIQUE")
            ):
                names.add(match.group(1))
        depth += line.count("(") - line.count(")")

    # `(?![a-z_])` so "column" does not also match "column_input"
    for stmt in re.findall(
        rf'ALTER TABLE\s+"?{table}"?(?![a-z_])(.*?);', sql, re.DOTALL | re.IGNORECASE
    ):
        for added in re.findall(r"ADD COLUMN\s+\"?([a-z_]+)\"?", stmt, re.IGNORECASE):
            names.add(added)
    return names


def test_every_mapper_configures():
    """Catches a bad relationship or a dangling string reference at import time."""
    configure_mappers()


def test_all_contract_tables_are_mapped():
    mapped = {t.name for t in Base.metadata.sorted_tables}
    assert MAPPED_TABLES <= mapped, f"unmapped: {sorted(MAPPED_TABLES - mapped)}"


@pytest.mark.parametrize("table", sorted(MAPPED_TABLES))
def test_model_columns_match_the_migration(table):
    expected = _columns_from_sql(table, _sql())
    actual = set(Base.metadata.tables[table].columns.keys())
    assert actual == expected, (
        f"{table}: ORM drifted from the locked schema — "
        f"missing {sorted(expected - actual)}, invented {sorted(actual - expected)}"
    )
