"""§7/§9/§11 source documents.

Case-scoped rather than sheet-scoped, because `document` hangs off `case_id`
(and optionally a `row_id`) — it has no sheet of its own. The per-row listing
lives with the rows, under its sheet.
"""

import uuid

from fastapi import APIRouter, HTTPException

from app.api.deps import DbSession
from app.models import Document
from app.schemas import DocumentOut
from app.services import grid_query

router = APIRouter(tags=["documents"])


@router.get(
    "/cases/{case_id}/documents",
    response_model=list[DocumentOut],
    summary="List a case's source documents",
)
async def list_case_documents(db: DbSession, case_id: uuid.UUID) -> list[DocumentOut]:
    if await grid_query.get_case(db, case_id) is None:
        raise HTTPException(status_code=404, detail=f"No case {case_id}")
    result = await db.scalars(grid_query.documents_of_case(case_id))
    return [DocumentOut.model_validate(d) for d in result]


@router.get(
    "/documents/{document_id}", response_model=DocumentOut, summary="Get one document"
)
async def get_document(db: DbSession, document_id: uuid.UUID) -> DocumentOut:
    """`external_ok` rides along — the client shows the gate, the server enforces
    it (§11). A document with `external_ok=false` is never sent to a provider."""
    document = await db.get(Document, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail=f"No document {document_id}")
    return DocumentOut.model_validate(document)
