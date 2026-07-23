"""§6a — lot grain, deterministic winner, identifier discipline.

All pure extraction over a recorded payload shape: no network, no LLM.
"""

import uuid

from app.connectors.prozorro import extract_lot_rows
from app.models.enums import CellStatus
from app.recipes.row_producing.prozorro_lots import (
    SLOT_PARTICIPANTS,
    SLOT_WINNER,
    ProzorroLots,
)

TENDER_WITH_LOTS = {
    "id": "abc123",
    "tenderID": "UA-2026-01-01-000001",
    "title": "Закупівля робіт",
    "dateModified": "2026-01-05T10:00:00+02:00",
    "lots": [
        {"id": "lot-1", "title": "Лот 1", "status": "active"},
        {"id": "lot-2", "title": "Лот 2", "status": "active"},
    ],
    "awards": [
        {
            "status": "active",
            "lotID": "lot-1",
            "value": {"amount": 1000.0, "currency": "UAH"},
            "suppliers": [
                {"identifier": {"scheme": "UA-EDR", "id": "12345678", "legalName": "ТОВ А"}}
            ],
        },
        {
            "status": "cancelled",
            "lotID": "lot-2",
            "value": {"amount": 999.0, "currency": "UAH"},
            "suppliers": [
                {"identifier": {"scheme": "UA-EDR", "id": "87654321", "legalName": "ТОВ Б"}}
            ],
        },
    ],
    "bids": [
        {
            "lotValues": [{"relatedLot": "lot-1"}],
            "tenderers": [
                {"identifier": {"scheme": "UA-EDR", "id": "12345678", "legalName": "ТОВ А"}},
                {"identifier": {"scheme": "UA-EDR", "id": "87654321", "legalName": "ТОВ Б"}},
            ],
        },
        {
            "lotValues": [{"relatedLot": "lot-2"}],
            "tenderers": [
                {"identifier": {"scheme": "UA-EDR", "id": "11112222", "legalName": "ТОВ В"}}
            ],
        },
    ],
}

TENDER_WITHOUT_LOTS = {
    "id": "def456",
    "tenderID": "UA-2026-01-01-000002",
    "title": "Пряма закупівля",
    "awards": [
        {
            "status": "active",
            "lotID": None,
            "value": {"amount": 500.0, "currency": "UAH"},
            "suppliers": [
                {"identifier": {"scheme": "XX-FOREIGN", "id": "FR-999", "legalName": "SARL"}}
            ],
        }
    ],
    "bids": [],
}


def test_one_row_per_lot():
    rows = extract_lot_rows(TENDER_WITH_LOTS)
    assert [r.lot_id for r in rows] == ["lot-1", "lot-2"]
    assert all(r.tender_id == "UA-2026-01-01-000001" for r in rows)


def test_tender_without_lots_still_yields_exactly_one_row():
    rows = extract_lot_rows(TENDER_WITHOUT_LOTS)
    assert len(rows) == 1
    assert rows[0].lot_id is None
    assert rows[0].provenance == {
        "source": "prozorro",
        "tenderID": "UA-2026-01-01-000002",
        "lotID": None,
    }


def test_winner_requires_active_status_and_a_matching_lot_id():
    lot1, lot2 = extract_lot_rows(TENDER_WITH_LOTS)
    assert lot1.winner_edrpou == "12345678"
    assert lot1.amount == {"amount": 1000.0, "currency": "UAH"}
    # lot-2's only award is cancelled — no winner leaks across from lot-1.
    assert lot2.winners == []
    assert lot2.amount is None


def test_participants_are_scoped_to_the_lot():
    lot1, lot2 = extract_lot_rows(TENDER_WITH_LOTS)
    assert [p.id for p in lot1.participants] == ["12345678", "87654321"]
    assert [p.id for p in lot2.participants] == ["11112222"]


def test_non_ua_edr_winner_is_not_an_edrpou():
    [row] = extract_lot_rows(TENDER_WITHOUT_LOTS)
    assert row.winner_edrpou is None
    assert row.has_out_of_scope_winner is True


async def test_recipe_emits_not_applicable_for_an_out_of_scope_winner():
    # §16 #9 — out of registry scope, not "we couldn't find it".
    recipe = ProzorroLots()
    [row] = extract_lot_rows(TENDER_WITHOUT_LOTS)
    produced = recipe._to_produced_row(row)
    assert produced.values[SLOT_WINNER].status is CellStatus.NotApplicable


async def test_recipe_emits_an_empty_list_as_answered():
    # §5/§2a — [] + Answered asserts a fact; it is not an empty cell.
    recipe = ProzorroLots()
    [row] = extract_lot_rows(TENDER_WITHOUT_LOTS)
    produced = recipe._to_produced_row(row)
    participants = produced.values[SLOT_PARTICIPANTS]
    assert participants.value == []
    assert participants.status is CellStatus.Answered


async def test_recipe_pulls_lots_through_a_stubbed_client():
    class StubClient:
        async def lot_rows(self, tender_id):
            return extract_lot_rows(TENDER_WITH_LOTS)

    rows = await ProzorroLots(client=StubClient()).produce(
        uuid.uuid4(), uuid.uuid4(), {"tender_ids": ["UA-2026-01-01-000001"]}
    )
    assert [r.provenance["lotID"] for r in rows] == ["lot-1", "lot-2"]
    assert all(r.depth == 0 for r in rows)
