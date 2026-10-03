"""
Audit log repository — intentionally exposes only `add` (insert) at this
layer; no update/delete methods are defined at all, reinforcing the
append-only design even before the database grants are applied.
"""
from __future__ import annotations

from app.models.audit_log import AuditLog
from app.repositories.base import BaseRepository


class AuditLogRepository(BaseRepository[AuditLog]):
    model = AuditLog

    async def delete(self, instance) -> None:  # type: ignore[override]
        raise NotImplementedError("Audit log entries are append-only and cannot be deleted.")
