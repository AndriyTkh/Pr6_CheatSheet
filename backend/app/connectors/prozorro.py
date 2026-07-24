"""Prozorro connector — §6a. Public API, no auth, no LLM.

Everything here is deterministic structured extraction: the winner, the amount
and the bidder list come out of the JSON by rule, not by model (§7 hybrid, §3
"not everything is an LLM").

**Identifier discipline (§6a).** `identifier` is `{scheme, id, legalName}` and
`id` is an EDRPOU *only* when `scheme == 'UA-EDR'`. The pair is always kept
together; a non-`UA-EDR` bidder is `NotApplicable` — out of registry scope — and
never `NotFound`, which would send the journalist hunting for a record that
cannot exist (§5, §16 #9).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Mapping, Sequence

import httpx

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "https://public.api.openprocurement.org/api/2.5"
UA_EDR = "UA-EDR"
FEED_BATCH = 100  # §6a


# =====================================================================
# Value objects — what one lot row carries
# =====================================================================


@dataclass(frozen=True, slots=True)
class Identifier:
    """`{scheme, id, legalName}` kept as a pair, never flattened to a bare id."""

    scheme: str | None
    id: str | None
    legal_name: str | None = None

    @property
    def is_edrpou(self) -> bool:
        """Only a `UA-EDR` identifier is a YouControl-keyable EDRPOU (§6a)."""
        return self.scheme == UA_EDR and bool(self.id)

    @classmethod
    def parse(cls, raw: Mapping[str, Any] | None) -> "Identifier | None":
        if not raw:
            return None
        return cls(
            scheme=raw.get("scheme"),
            id=raw.get("id"),
            legal_name=raw.get("legalName"),
        )

    def to_jsonb(self) -> dict[str, Any]:
        return {"scheme": self.scheme, "id": self.id, "legalName": self.legal_name}


@dataclass(slots=True)
class LotRow:
    """One row (§16 #3). A tender with no `lots[]` yields exactly one, `lot_id=None`."""

    tender_id: str
    lot_id: str | None
    tender_title: str | None
    lot_title: str | None
    procuring_entity: Mapping[str, Any] | None
    date_modified: str | None
    status: str | None
    #: `award.value` for this lot — `{amount, currency}`
    amount: Mapping[str, Any] | None = None
    #: deterministic per-lot winner, `UA-EDR` filtered
    winners: list[Identifier] = field(default_factory=list)
    #: `@participants` — what Expand consumes (§2a)
    participants: list[Identifier] = field(default_factory=list)
    documents: list[Mapping[str, Any]] = field(default_factory=list)

    @property
    def provenance(self) -> dict[str, Any]:
        """Row key (§16 #3). `row.tender_id`/`lot_id` are generated from this."""
        return {
            "source": "prozorro",
            "tenderID": self.tender_id,
            "lotID": self.lot_id,
        }

    @property
    def winner_edrpou(self) -> str | None:
        return next((w.id for w in self.winners if w.is_edrpou), None)

    @property
    def has_out_of_scope_winner(self) -> bool:
        """True when a winner exists but none of them is registry-keyable.

        Drives `NotApplicable` rather than `NotFound` on registry columns (§6a).
        """
        return bool(self.winners) and not any(w.is_edrpou for w in self.winners)


# =====================================================================
# Client
# =====================================================================


class ProzorroClient:
    """Thin async client over the public read API. No key, no secrets (§11)."""

    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        client: httpx.AsyncClient | None = None,
        timeout: float = 30.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self._client = client
        self._owns_client = client is None
        self._timeout = timeout

    async def __aenter__(self) -> "ProzorroClient":
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self._timeout)
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        if self._owns_client and self._client is not None:
            await self._client.aclose()
            self._client = None

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self._timeout)
        return self._client

    async def _get(self, path: str, params: Mapping[str, Any] | None = None) -> dict:
        response = await self.client.get(
            f"{self.base_url}{path}", params=dict(params or {})
        )
        response.raise_for_status()
        return response.json()

    async def feed(
        self,
        offset: str | None = None,
        limit: int = FEED_BATCH,
        descending: bool = False,
    ) -> AsyncIterator[tuple[list[dict], str | None]]:
        """`GET /tenders` — sync-by-`dateModified`, cursor `next_page.offset` (§6a).

        Yields `(batch, next_offset)`. Stops when a page comes back empty; the
        caller persists `next_offset` and resumes from it on the next poll
        (~5 min), so a restart never re-walks the whole feed.

        `descending` walks newest-first instead. Not for syncing — resuming a
        descending cursor would miss everything published while you were away —
        but it is how you reach today's tenders without replaying 2015.
        """
        while True:
            params: dict[str, Any] = {"limit": limit}
            if descending:
                params["descending"] = 1
            if offset:
                params["offset"] = offset
            payload = await self._get("/tenders", params)
            batch = payload.get("data", [])
            offset = (payload.get("next_page") or {}).get("offset")
            yield batch, offset
            if not batch:
                return

    async def tender(self, tender_id: str) -> dict:
        """`GET /tenders/{id}` — the full package."""
        return (await self._get(f"/tenders/{tender_id}")).get("data", {})

    async def documents(self, tender_id: str) -> list[dict]:
        """`GET /tenders/{id}/documents` — feeds upload/OCR/Extract (§7)."""
        return (await self._get(f"/tenders/{tender_id}/documents")).get("data", [])

    async def lot_rows(self, tender_id: str) -> list[LotRow]:
        """One real tender → its lot row(s), fully extracted."""
        return extract_lot_rows(await self.tender(tender_id))


# =====================================================================
# Extraction — pure functions over the tender JSON (unit-testable, no network)
# =====================================================================


def extract_lot_rows(tender: Mapping[str, Any]) -> list[LotRow]:
    """§16 #3 — one row per lot; a tender with no `lots[]` still yields one row.

    Pure: hand it a recorded tender payload and the whole extraction is testable
    without touching the network.
    """
    tender_id = tender.get("tenderID") or tender.get("id") or ""
    lots: Sequence[Mapping[str, Any]] = tender.get("lots") or []
    documents = list(tender.get("documents") or [])

    if not lots:
        return [
            _build_row(
                tender=tender,
                tender_id=tender_id,
                lot=None,
                documents=documents,
            )
        ]

    return [
        _build_row(tender=tender, tender_id=tender_id, lot=lot, documents=documents)
        for lot in lots
    ]


def _build_row(
    *,
    tender: Mapping[str, Any],
    tender_id: str,
    lot: Mapping[str, Any] | None,
    documents: list[Mapping[str, Any]],
) -> LotRow:
    lot_id = lot.get("id") if lot else None
    amount, winners = extract_award(tender, lot_id)
    return LotRow(
        tender_id=tender_id,
        lot_id=lot_id,
        tender_title=tender.get("title"),
        lot_title=lot.get("title") if lot else None,
        procuring_entity=tender.get("procuringEntity"),
        date_modified=tender.get("dateModified"),
        status=(lot or tender).get("status"),
        amount=amount,
        winners=winners,
        participants=extract_participants(tender, lot_id),
        documents=documents,
    )


def extract_award(
    tender: Mapping[str, Any], lot_id: str | None
) -> tuple[Mapping[str, Any] | None, list[Identifier]]:
    """Deterministic winner + amount for one lot (§6a).

    The rule is exactly `award.status == 'active'` **and** `award.lotID == lot.id`
    — matching on status alone would attribute another lot's winner to this row.
    """
    for award in tender.get("awards") or []:
        if award.get("status") != "active":
            continue
        if award.get("lotID") != lot_id:
            continue
        suppliers = [
            ident
            for ident in (
                Identifier.parse(s.get("identifier")) for s in award.get("suppliers") or []
            )
            if ident is not None
        ]
        return award.get("value"), suppliers
    return None, []


def extract_participants(
    tender: Mapping[str, Any], lot_id: str | None
) -> list[Identifier]:
    """`@participants` for this lot — the list Expand consumes (§2a).

    Bids are filtered by `lotValues[].relatedLot`; a tender with no lots has no
    `lotValues`, so every bid belongs to the single row.
    """
    out: list[Identifier] = []
    seen: set[tuple[str | None, str | None]] = set()

    for bid in tender.get("bids") or []:
        if lot_id is not None:
            related = {lv.get("relatedLot") for lv in bid.get("lotValues") or []}
            if lot_id not in related:
                continue
        for tenderer in bid.get("tenderers") or []:
            ident = Identifier.parse(tenderer.get("identifier"))
            if ident is None:
                continue
            key = (ident.scheme, ident.id)
            if key in seen:
                continue
            seen.add(key)
            out.append(ident)
    return out
