"""
Organization — top-level tenant boundary.

WRDT may eventually be run for more than one NGO/federation on the same
backend. Every Region belongs to exactly one Organization, so multi-tenant
isolation is available from day one even though the current frontend only
ever renders a single organization's data. Nothing in the frontend needs to
change for this — it simply gives the backend a clean seam if/when a second
tenant is onboarded.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, SoftDeleteMixin, TimestampMixin, UUIDPKMixin



if TYPE_CHECKING:  # pragma: no cover - import cycle guard for relationship types
    from app.models.user import User
    from app.models.region import Region

class Organization(Base, UUIDPKMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "organizations"

    name: Mapped[str] = mapped_column(String(200), nullable=False, unique=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="Active")

    users: Mapped[list["User"]] = relationship(back_populates="organization")
    regions: Mapped[list["Region"]] = relationship(back_populates="organization")
