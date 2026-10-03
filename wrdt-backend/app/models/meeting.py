"""
Meeting — one "page" of a Group's register (fortnightly, by convention:
next meeting_date = previous + 15 days, matching the frontend's addDays()).

Sequencing + the permanent lock are enforced at the DATABASE level, not
just in application code:

  - `uq_meeting_no_per_group`: meeting_no is unique per group.
  - `uq_one_open_meeting_per_group`: a PARTIAL unique index guaranteeing at
    most one `status='in_progress'` meeting can exist per group at any
    time — this is exactly the frontend's
    `startNewMeetingForGroup` rule ("finish this week's page before
    starting next week's"), now impossible to violate even by a bug or a
    concurrent request.
  - `locked` + a BEFORE UPDATE/DELETE trigger on meeting_entries/expenses
    (added in the Alembic migration) makes the "irreversible lock" rule a
    hard database guarantee, matching the frontend's own comment: "the
    lock is permanent, even against bugs elsewhere in the app."
"""
from __future__ import annotations

from typing import TYPE_CHECKING

import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPKMixin



if TYPE_CHECKING:  # pragma: no cover - import cycle guard for relationship types
    from app.models.group import Group
    from app.models.meeting_entry import MeetingEntry
    from app.models.expense import Expense

class Meeting(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "meetings"
    __table_args__ = (
        UniqueConstraint("group_id", "meeting_no", name="uq_meeting_no_per_group"),
        # The partial unique index enforcing "one open meeting per group" is
        # added as raw SQL in the Alembic migration (Postgres partial
        # indexes with a WHERE clause aren't first-class in the declarative
        # __table_args__ across all SQLAlchemy versions in a fully portable
        # way) — see migrations/versions/0003_partial_indexes_and_triggers.py.
    )

    group_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("groups.id"), nullable=False
    )
    meeting_no: Mapped[int] = mapped_column(Integer, nullable=False)
    meeting_date: Mapped[date] = mapped_column(Date, nullable=False)
    supervisor_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )

    status: Mapped[str] = mapped_column(String(20), nullable=False, default="in_progress")
    # 'in_progress' | 'completed' — mirrors ledger.completed in the frontend
    locked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    group: Mapped["Group"] = relationship(back_populates="meetings")
    entries: Mapped[list["MeetingEntry"]] = relationship(
        back_populates="meeting", cascade="all, delete-orphan"
    )
    expenses: Mapped[list["Expense"]] = relationship(
        back_populates="meeting", cascade="all, delete-orphan"
    )
