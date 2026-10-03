"""
Group (SHG — Self Help Group) — belongs to a Region, contains Members.

Name uniqueness is scoped to Region (not global), matching
`createGroup`/`updateGroup`'s duplicate check in the frontend.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

import uuid
from datetime import date

from sqlalchemy import Date, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, SoftDeleteMixin, TimestampMixin, UUIDPKMixin



if TYPE_CHECKING:  # pragma: no cover - import cycle guard for relationship types
    from app.models.region import Region
    from app.models.member import Member
    from app.models.meeting import Meeting
    from app.models.user import UserGroupAssignment

class Group(Base, UUIDPKMixin, TimestampMixin, SoftDeleteMixin):
    """
    NOTE: case-insensitive name uniqueness within a region is enforced via a
    functional unique index on (region_id, lower(name)) — see
    migrations/versions/0002_functional_indexes.py.
    """

    __tablename__ = "groups"
    __table_args__ = (
        UniqueConstraint("region_id", "name", name="uq_group_name_per_region"),
    )

    region_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("regions.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    formed_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="Active")
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )

    region: Mapped["Region"] = relationship(back_populates="groups")
    members: Mapped[list["Member"]] = relationship(back_populates="group")
    meetings: Mapped[list["Meeting"]] = relationship(back_populates="group")
    assigned_users: Mapped[list["UserGroupAssignment"]] = relationship(back_populates="group")
