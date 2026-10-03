"""
Region — top of the Region > Group > Member hierarchy.

Name uniqueness is scoped to Organization (case-insensitive), matching the
frontend's `createRegion`/`updateRegion` duplicate check — the mock today
is effectively single-org, so this is a strict superset of that rule, not
a behavior change.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

import uuid

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, SoftDeleteMixin, TimestampMixin, UUIDPKMixin



if TYPE_CHECKING:  # pragma: no cover - import cycle guard for relationship types
    from app.models.organization import Organization
    from app.models.group import Group

class Region(Base, UUIDPKMixin, TimestampMixin, SoftDeleteMixin):
    """
    NOTE: case-insensitive name uniqueness (matching the frontend's
    `.toLowerCase()` duplicate check) is enforced via a functional unique
    index on lower(name), added as raw SQL in the Alembic migration rather
    than expressed here — SQLAlchemy's declarative class body can't cleanly
    reference `func.lower(self.name)` before the column exists. See
    migrations/versions/0002_functional_indexes.py.
    """

    __tablename__ = "regions"
    __table_args__ = (
        UniqueConstraint("organization_id", "name", name="uq_region_name_per_org"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="Active")
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )

    organization: Mapped["Organization"] = relationship(back_populates="regions")
    groups: Mapped[list["Group"]] = relationship(back_populates="region")
