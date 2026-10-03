"""
Role — RBAC role definitions.

Modeled as a table (not a bare enum) so permissions are data, not code —
new roles or permission tweaks are a migration + seed update, not a
redeploy. WRDT v1.0 ships with exactly two seeded roles:

  owner       - full system access (Region/Group/Member CRUD, Excel Import,
                User Management, Settings, Reports)
  supervisor  - login, view assigned groups, run the meeting workflow
                (start/draft/update/complete), view reports; NO region/group
                deletion or system administration

`permissions` is a JSONB bag of permission keys rather than a fixed set of
boolean columns, so Phase 3+ can introduce finer-grained permissions later
without a schema migration.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPKMixin



if TYPE_CHECKING:  # pragma: no cover - import cycle guard for relationship types
    from app.models.user import User

class Role(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "roles"

    name: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)  # 'owner' | 'supervisor'
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)
    permissions: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    users: Mapped[list["User"]] = relationship(back_populates="role")
