"""
MeetingEntry — one member's row within one meeting's ledger
(a "cell-row" of the paper register). This is the heart of the savings +
loan workflow and the single most business-rule-dense table in the schema.

Column-by-column mapping back to the frontend's ledger row shape
(`getLedger()` / `ledgerTotals()` in the WRDT_Modules2to8 source):

  prev_saving             <- r.prevSaving   (opening saving, carried forward)
  cur_saving               <- r.curSaving    (this meeting's collection)
  loan_given                <- r.loan         (Loan Given, blank/0 by default)
  principal_paid            <- r.install       (Principal Paid)
  interest_paid             <- r.interest      (Interest)
  paid_till_date_opening    <- r.paidTillDateOpening (cumulative, BEFORE this meeting)
  loan_remaining_opening    <- r.loanRemainingOpening
  loan_remaining            <- r.loanRemaining  (auto OR manually overridden — see below)
  loan_remaining_manual     <- r.loanRemainingManual (flag: frozen from auto-recalc)
  fine                      <- r.fine
  remarks                   <- r.remarks

Derived values (NOT stored — always computed server-side by the ledger
engine service in Phase 7, exactly like `rowCashPaid()`/`ledgerTotals()`):
  row_cash_paid = cur_saving + principal_paid + fine + interest_paid
  auto loan_remaining = loan_remaining_opening + loan_given - principal_paid
    (used only while loan_remaining_manual = FALSE)

Carry-forward (computed once, at meeting-start time, by the meeting
service — never by a trigger, since it needs cross-table read access to
the PREVIOUS meeting's entries):
  next.prev_saving            = this.prev_saving + this.cur_saving
  next.loan_remaining_opening = this.loan_remaining   (whatever value froze)
  next.paid_till_date_opening = this.paid_till_date_opening + this.principal_paid
"""
from __future__ import annotations

from typing import TYPE_CHECKING

import uuid

from sqlalchemy import Boolean, ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPKMixin



if TYPE_CHECKING:  # pragma: no cover - import cycle guard for relationship types
    from app.models.meeting import Meeting
    from app.models.member import Member

class MeetingEntry(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "meeting_entries"
    __table_args__ = (
        UniqueConstraint("meeting_id", "member_id", name="uq_entry_per_member_per_meeting"),
    )

    meeting_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("meetings.id"), nullable=False
    )
    member_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("members.id"), nullable=False
    )

    present: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    prev_saving: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    cur_saving: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, default=0)

    loan_given: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    principal_paid: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    interest_paid: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, default=0)

    paid_till_date_opening: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    loan_remaining_opening: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    loan_remaining: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    loan_remaining_manual: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    fine: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    remarks: Mapped[str] = mapped_column(String(255), nullable=False, default="Paid")

    meeting: Mapped["Meeting"] = relationship(back_populates="entries")
    member: Mapped["Member"] = relationship(back_populates="ledger_entries")
