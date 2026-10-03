"""
User — an authenticated operator of the system (Owner or Supervisor).

A Supervisor is scoped to specific Groups via `user_group_assignments`
(many-to-many) — this matches "View Assigned Groups" in the permission
spec: a supervisor may run meetings for more than one group, and a group
may (over time) have more than one supervisor associated with its history,
so this is modeled as a proper join table rather than a single FK on
either side.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

import uuid

from sqlalchemy import Boolean, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, SoftDeleteMixin, TimestampMixin, UUIDPKMixin



if TYPE_CHECKING:  # pragma: no cover - import cycle guard for relationship types
    from app.models.organization import Organization
    from app.models.role import Role
    from app.models.group import Group

class User(Base, UUIDPKMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "users"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False
    )
    role_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("roles.id"), nullable=False
    )

    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(200), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    organization: Mapped["Organization"] = relationship(back_populates="users")
    role: Mapped["Role"] = relationship(back_populates="users")
    assigned_groups: Mapped[list["UserGroupAssignment"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class UserGroupAssignment(Base, UUIDPKMixin, TimestampMixin):
    """Join table: which Supervisor(s) are assigned to which Group(s)."""

    __tablename__ = "user_group_assignments"
    __table_args__ = (
        UniqueConstraint("user_id", "group_id", name="uq_user_group_assignment"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    group_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("groups.id"), nullable=False
    )

    user: Mapped["User"] = relationship(back_populates="assigned_groups")
    group: Mapped["Group"] = relationship(back_populates="assigned_users")
