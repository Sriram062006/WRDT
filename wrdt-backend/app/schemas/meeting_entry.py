from __future__ import annotations

import uuid
from decimal import Decimal

from pydantic import BaseModel, Field

from app.schemas.base import TimestampedRead


class MeetingEntryRead(TimestampedRead):
    meeting_id: uuid.UUID
    member_id: uuid.UUID
    present: bool
    prev_saving: Decimal
    cur_saving: Decimal
    loan_given: Decimal
    principal_paid: Decimal
    interest_paid: Decimal
    paid_till_date_opening: Decimal
    loan_remaining_opening: Decimal
    loan_remaining: Decimal
    loan_remaining_manual: bool
    fine: Decimal
    remarks: str


class MeetingEntryDraftUpdate(BaseModel):
    """Fields a Supervisor may edit while a meeting is in_progress (auto-save
    draft). Rejected with MeetingLockedError (409) if the meeting is locked --
    enforced in the service layer AND by the database trigger.

    Every money field is `ge=0`: these are cash amounts counted on a table,
    and a negative saving/fine/repayment has no meaning in the register.
    Without the bound, a typo'd minus sign would silently corrupt the
    group's carry-forward for every future meeting."""

    present: bool | None = None
    cur_saving: Decimal | None = Field(None, ge=0)
    loan_given: Decimal | None = Field(None, ge=0)
    principal_paid: Decimal | None = Field(None, ge=0)
    interest_paid: Decimal | None = Field(None, ge=0)
    fine: Decimal | None = Field(None, ge=0)
    remarks: str | None = Field(None, max_length=255)


class BulkEntryItem(MeetingEntryDraftUpdate):
    member_id: uuid.UUID


class BulkEntryUpdate(BaseModel):
    """Whole-sheet save. Capped at 500 rows so one request can't be used
    to hold a transaction open indefinitely."""

    entries: list[BulkEntryItem] = Field(..., max_length=500)


class LoanOverrideRequest(BaseModel):
    loan_remaining: Decimal = Field(..., ge=0)


class LedgerTotals(BaseModel):
    """Server-computed totals — the ONE place these numbers are calculated,
    mirroring the frontend's ledgerTotals(). Never trust a client-supplied
    total; always recompute from meeting_entries/expenses."""

    tot_prev_saving: Decimal
    tot_savings: Decimal
    tot_total_saving: Decimal
    tot_loan: Decimal
    tot_paid_till_date: Decimal
    tot_install: Decimal
    tot_interest: Decimal
    tot_fine: Decimal
    tot_expense: Decimal
    tot_cash_coll: Decimal
    cash_in_hand: Decimal
    loan_remaining: Decimal
    present: int
    absent: int
