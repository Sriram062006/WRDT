"""
Audit logging service — the single call site every mutating service method
uses to record a change (see AuditLogRepository: insert-only, no
update/delete methods exist on it at all).
"""
from __future__ import annotations

import uuid

from app.models.audit_log import AuditLog
from app.repositories.audit_repo import AuditLogRepository


class AuditService:
    def __init__(self, db):
        self.repo = AuditLogRepository(db)

    async def record(
        self,
        *,
        actor_id: uuid.UUID | None,
        action: str,
        entity_type: str,
        entity_id: uuid.UUID,
        before: dict | None = None,
        after: dict | None = None,
    ) -> None:
        entry = AuditLog(
            actor_id=actor_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            before_state=before,
            after_state=after,
        )
        self.repo.add(entry)
        await self.repo.flush()
