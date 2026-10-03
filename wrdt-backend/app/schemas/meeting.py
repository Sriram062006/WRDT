from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel

from app.schemas.base import TimestampedRead
from app.schemas.expense import ExpenseRead
from app.schemas.meeting_entry import LedgerTotals, MeetingEntryRead


class MeetingRead(TimestampedRead):
    group_id: uuid.UUID
    meeting_no: int
    meeting_date: date
    supervisor_id: uuid.UUID | None
    status: str
    locked: bool
    completed_at: datetime | None


class MeetingDetail(MeetingRead):
    """Full payload for the Meeting Register screen: rows + expenses +
    server-computed totals, all in one response so the frontend never has
    to (and never could) compute these numbers itself."""

    entries: list[MeetingEntryRead]
    expenses: list[ExpenseRead]
    totals: LedgerTotals


class MeetingListItem(BaseModel):
    """Lightweight shape for the Meetings List screen: enough to render the
    row (including its headline totals) without shipping every ledger
    entry. The totals are aggregated in SQL, not recomputed per meeting in
    Python, so listing a group with 40 meetings stays one query."""

    id: uuid.UUID
    group_id: uuid.UUID
    meeting_no: int
    meeting_date: date
    status: str
    locked: bool
    supervisor_id: uuid.UUID | None = None
    members_present: int = 0
    members_total: int = 0
    total_saving: Decimal = Decimal("0")
    total_loan: Decimal = Decimal("0")
    total_expense: Decimal = Decimal("0")
    cash_in_hand: Decimal = Decimal("0")
