"""The row-producing recipe that seeds the `@tenders` sheet (§6, §6a).

`func` shape — no LLM anywhere in this path. It emits one row per tender lot
(§16 #3) with the deterministic connector columns already filled, each carrying
an API citation back to the exact Prozorro field it came from (§9).
"""

from __future__ import annotations

import uuid
from typing import Any, ClassVar, Mapping, Sequence

from app.connectors.prozorro import DEFAULT_BASE_URL, LotRow, ProzorroClient
from app.models.enums import CellStatus, RecipeExecType
from app.recipes.base import (
    Citation,
    CellResult,
    OutputSlot,
    ProducedRow,
    RowProducingRecipe,
)

#: The connector columns this recipe seeds onto the source sheet.
SLOT_TENDER = "tender"
SLOT_LOT = "lot"
SLOT_AMOUNT = "amount"
SLOT_WINNER = "winner_edrpou"
SLOT_PARTICIPANTS = "participants"


class ProzorroLots(RowProducingRecipe):
    """Prozorro → one row per tender lot, zero LLM (§6a)."""

    id: ClassVar[str] = "prozorro_lots"
    name: ClassVar[str] = "Prozorro — тендерні лоти"
    version: ClassVar[int] = 1
    exec_type: ClassVar[RecipeExecType] = RecipeExecType.func
    volatile: ClassVar[bool] = False

    outputs: ClassVar[Sequence[OutputSlot]] = (
        OutputSlot(SLOT_TENDER, "text", description="tenderID"),
        OutputSlot(SLOT_LOT, "text", description="Назва лоту"),
        OutputSlot(SLOT_AMOUNT, "money", description="award.value"),
        OutputSlot(SLOT_WINNER, "text", description="EDRPOU переможця (UA-EDR)"),
        # a typed list — Expand consumes it, Formula/Compute may count it (§2a)
        OutputSlot(
            SLOT_PARTICIPANTS,
            "list",
            item_type="identifier",
            description="@participants — учасники лоту",
        ),
    )

    params_schema: ClassVar[Mapping[str, Any]] = {
        "type": "object",
        "properties": {
            "tender_ids": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Explicit tender ids to pull (pilot case).",
            },
            "base_url": {"type": "string", "default": DEFAULT_BASE_URL},
        },
        "required": ["tender_ids"],
        "additionalProperties": False,
    }

    output_schema: ClassVar[Mapping[str, Any]] = {
        "type": "object",
        "properties": {
            SLOT_TENDER: {"type": ["string", "null"]},
            SLOT_LOT: {"type": ["string", "null"]},
            SLOT_AMOUNT: {
                "type": ["object", "null"],
                "properties": {
                    "amount": {"type": ["number", "null"]},
                    "currency": {"type": ["string", "null"]},
                },
            },
            SLOT_WINNER: {"type": ["string", "null"]},
            SLOT_PARTICIPANTS: {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "scheme": {"type": ["string", "null"]},
                        "id": {"type": ["string", "null"]},
                        "legalName": {"type": ["string", "null"]},
                    },
                },
            },
        },
        "required": [SLOT_TENDER, SLOT_PARTICIPANTS],
        "additionalProperties": False,
    }

    cite_spec: ClassVar[Mapping[str, Any]] = {
        SLOT_AMOUNT: "awards[status=active,lotID=<lot>].value",
        SLOT_WINNER: "awards[status=active,lotID=<lot>].suppliers[].identifier.id",
        SLOT_PARTICIPANTS: "bids[lotValues.relatedLot=<lot>].tenderers[].identifier",
    }

    def __init__(self, client: ProzorroClient | None = None) -> None:
        self._client = client

    async def produce(
        self, case_id: uuid.UUID, sheet_id: uuid.UUID, params: Mapping[str, Any]
    ) -> Sequence[ProducedRow]:
        self.validate_params(params)
        tender_ids: list[str] = list(params["tender_ids"])
        base_url = params.get("base_url", DEFAULT_BASE_URL)

        client = self._client or ProzorroClient(base_url=base_url)
        owns = self._client is None
        try:
            rows: list[ProducedRow] = []
            for tender_id in tender_ids:
                for lot_row in await client.lot_rows(tender_id):
                    rows.append(self._to_produced_row(lot_row))
            return rows
        finally:
            if owns:
                await client.aclose()

    # -----------------------------------------------------------------

    def _to_produced_row(self, lot: LotRow) -> ProducedRow:
        return ProducedRow(
            provenance=lot.provenance,
            depth=0,
            values={
                SLOT_TENDER: CellResult(
                    slot=SLOT_TENDER,
                    value=lot.tender_id,
                    status=CellStatus.Answered,
                    citations=[self._cite(lot, "tenderID")],
                ),
                SLOT_LOT: self._lot_title(lot),
                SLOT_AMOUNT: self._amount(lot),
                SLOT_WINNER: self._winner(lot),
                SLOT_PARTICIPANTS: self._participants(lot),
            },
        )

    def _lot_title(self, lot: LotRow) -> CellResult:
        if lot.lot_id is None:
            # A tender without lots is one row by design, not a missing lot (§6a).
            return CellResult(
                slot=SLOT_LOT,
                value=lot.tender_title,
                status=CellStatus.Answered,
                citations=[self._cite(lot, "title")],
            )
        return CellResult(
            slot=SLOT_LOT,
            value=lot.lot_title,
            status=CellStatus.Answered,
            citations=[self._cite(lot, f"lots[id={lot.lot_id}].title")],
        )

    def _amount(self, lot: LotRow) -> CellResult:
        if lot.amount is None:
            # No active award yet — the question applies, the answer isn't there.
            return CellResult(
                slot=SLOT_AMOUNT,
                value=None,
                status=CellStatus.NotFound,
                message="Немає активного award для цього лоту.",
            )
        return CellResult(
            slot=SLOT_AMOUNT,
            value=dict(lot.amount),
            status=CellStatus.Answered,
            citations=[self._cite(lot, self.cite_spec[SLOT_AMOUNT])],
        )

    def _winner(self, lot: LotRow) -> CellResult:
        edrpou = lot.winner_edrpou
        if edrpou:
            return CellResult(
                slot=SLOT_WINNER,
                value=edrpou,
                status=CellStatus.Answered,
                citations=[self._cite(lot, self.cite_spec[SLOT_WINNER])],
            )
        if lot.has_out_of_scope_winner:
            # §6a/§16 #9 — a foreign or non-registry bidder is out of scope, not
            # missing. Downgrading this to NotFound would send the journalist
            # looking for a registry record that cannot exist.
            return CellResult(
                slot=SLOT_WINNER,
                value=None,
                status=CellStatus.NotApplicable,
                message="Переможець поза реєстром UA-EDR (інша схема ідентифікатора).",
            )
        return CellResult(
            slot=SLOT_WINNER,
            value=None,
            status=CellStatus.NotFound,
            message="Переможця не визначено.",
        )

    def _participants(self, lot: LotRow) -> CellResult:
        # An empty list with status Answered is a real answer — "we looked, there
        # are none" — and is distinct from NotFound/InsufficientData (§5, §2a).
        return CellResult(
            slot=SLOT_PARTICIPANTS,
            value=[p.to_jsonb() for p in lot.participants],
            status=CellStatus.Answered,
            citations=[
                self._cite(lot, self.cite_spec[SLOT_PARTICIPANTS])
                for _ in lot.participants
            ],
        )

    def _cite(self, lot: LotRow, api_path: str) -> Citation:
        return Citation(
            source_type="api",
            api_path=f"prozorro:/tenders/{lot.tender_id}#{api_path}",
            url=f"https://prozorro.gov.ua/tender/{lot.tender_id}",
        )
