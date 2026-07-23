"""§7/§9/§11 — source documents. `external_ok` is the hard gate, so it ships."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    case_id: uuid.UUID
    #: package documents hang off their row (§6)
    row_id: uuid.UUID | None
    url: str | None
    doc_type: str | None
    format: str | None
    storage_key: str | None
    has_text_layer: bool | None
    #: null | pending | ok | failed (§7)
    ocr_status: str | None
    source_lang: str | None
    #: §11 hard gate — false blocks the document from any external provider
    external_ok: bool
    created_at: datetime
