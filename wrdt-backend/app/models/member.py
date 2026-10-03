"""
Member — belongs to a Group; the person whose savings/loan history is
tracked meeting-over-meeting.

`seed_*` columns exist ONLY to bootstrap a member's very first meeting's
opening balances (mirrors the frontend's `prevSaving`/`loan`/`install`/
`fine` fields on the MEMBERS array). After a member's first
MeetingLedgerEntry is created, all further carry-forward reads from
meeting_entries, never from these seed columns again — see Meeting/
MeetingEntry models.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

import uuid
from datetime import date

from sqlalchemy import Date, ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, SoftDeleteMixin, TimestampMixin, UUIDPKMixin



if TYPE_CHECKING:  # pragma: no cover - import cycle guard for relationship types
    from app.models.group import Group
    from app.models.meeting_entry import MeetingEntry

class Member(Base, UUIDPKMixin, TimestampMixin, SoftDeleteMixin):
    """
    NOTE: case-insensitive name uniqueness within a group is enforced via a
    functional unique index on (group_id, lower(name)) — see
    migrations/versions/0002_functional_indexes.py.
    """

    __tablename__ = "members"
    __table_args__ = (
        UniqueConstraint("group_id", "name", name="uq_member_name_per_group"),
    )

    group_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("groups.id"), nullable=False
    )
    code: Mapped[str] = mapped_column(String(20), nullable=False)  # e.g. LM001
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    joined_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="Active")

    # Bootstrap-only seed values — see module docstring.
    seed_prev_saving: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    seed_loan: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    seed_install: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    seed_fine: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, default=0)

    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )

    group: Mapped["Group"] = relationship(back_populates="members")
    ledger_entries: Mapped[list["MeetingEntry"]] = relationship(back_populates="member")
