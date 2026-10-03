"""
AuditLog — append-only record of every meaningful state change in the
system (meeting completion, loan overrides, CRUD, imports, auth events).

Uses (entity_type, entity_id) instead of a per-table FK so new auditable
entities can be added later without a schema migration. `before_state`/
`after_state` are full JSONB snapshots, giving a queryable diff
(`before_state->>'loan_remaining'`) without dedicated per-field audit
columns.

Deletion/mutation of rows in this table is blocked at the database grant
level (the API's runtime role is only granted INSERT/SELECT on
audit_logs) — see migrations/versions/0004_audit_log_permissions.py.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import INET, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    action: Mapped[str] = mapped_column(String(100), nullable=False)  # e.g. 'meeting.complete'
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)  # 'meeting'|'member'|...
    entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)

    before_state: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    after_state: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    ip_address: Mapped[str | None] = mapped_column(INET, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
