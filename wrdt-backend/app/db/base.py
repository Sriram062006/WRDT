"""
Declarative base + shared mixins for all ORM models.

Importing every model module here (at the bottom) ensures Alembic's
autogenerate can discover the full metadata graph from a single import,
without each model needing to be manually registered anywhere else.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class UUIDPKMixin:
    """Standard UUID primary key used by every table in the system."""

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )


class TimestampMixin:
    """created_at / updated_at, server-generated, always present."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class SoftDeleteMixin:
    """
    Soft delete instead of hard delete.

    Business justification (flagged during architecture review): a Region/
    Group/Member that is deactivated must not break referential integrity
    for locked, historical meetings that reference it. Hard-deleting a
    member who has completed-meeting history would violate the "permanent
    record" rule the ledger already enforces. All repository `.delete()`
    methods set `deleted_at` rather than issuing a SQL DELETE.
    """

    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None


# All ORM models are imported centrally via `app/models/__init__.py`, which
# Alembic's env.py imports before calling `Base.metadata` — see
# app/db/migrations/env.py.
