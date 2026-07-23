"""§11 case — the container a set of sheets hangs off (§2a)."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class CaseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    owner_id: uuid.UUID
    is_private: bool
    created_at: datetime
