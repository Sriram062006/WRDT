from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel


class AuditLogRead(BaseModel):
    id: int
    actor_id: uuid.UUID | None
    action: str
    entity_type: str
    entity_id: uuid.UUID
    before_state: dict | None
    after_state: dict | None
    created_at: datetime

    model_config = {"from_attributes": True}
