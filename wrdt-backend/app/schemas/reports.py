from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from pydantic import BaseModel


class DashboardStats(BaseModel):
    """Replaces the frontend's static Dashboard mock data with real,
    live-computed figures — same shape the StatCards/charts expect."""

    total_regions: int
    total_groups: int
    total_members: int
    active_meetings: int  # currently in_progress, across the organization
    total_savings: Decimal
    total_loans_outstanding: Decimal
    todays_collection: Decimal
    meetings_completed_this_month: int


class MemberLedgerRow(BaseModel):
    meeting_id: uuid.UUID
    meeting_no: int
    meeting_date: date
    present: bool
    prev_saving: Decimal
    cur_saving: Decimal
    loan_given: Decimal
    principal_paid: Decimal
    interest_paid: Decimal
    loan_remaining: Decimal
    fine: Decimal
    cash_paid: Decimal


class MemberLedgerReport(BaseModel):
    member_id: uuid.UUID
    member_name: str
    group_id: uuid.UUID
    group_name: str
    rows: list[MemberLedgerRow]
    current_savings_balance: Decimal
    current_loan_remaining: Decimal


class LoanLedgerEntry(BaseModel):
    member_id: uuid.UUID
    member_name: str
    group_id: uuid.UUID
    group_name: str
    region_id: uuid.UUID
    region_name: str
    loan_remaining: Decimal
    loan_remaining_manual: bool
    as_of_meeting_no: int
    as_of_meeting_date: date


class LoanLedgerReport(BaseModel):
    """Outstanding loans across every member with a nonzero remaining
    balance, as of each member's most recent meeting entry."""

    entries: list[LoanLedgerEntry]
    total_outstanding: Decimal


class GroupReport(BaseModel):
    group_id: uuid.UUID
    group_name: str
    meetings_count: int
    total_savings_collected: Decimal
    total_loans_disbursed: Decimal
    total_loan_repaid: Decimal
    total_interest_collected: Decimal = Decimal("0")
    total_fines_collected: Decimal = Decimal("0")
    total_expenses: Decimal
    current_loan_outstanding: Decimal


class RegionReport(BaseModel):
    region_id: uuid.UUID
    region_name: str
    groups_count: int
    members_count: int
    total_savings_collected: Decimal
    total_loans_disbursed: Decimal
    total_expenses: Decimal
    current_loan_outstanding: Decimal


class MonthlyReport(BaseModel):
    year: int
    month: int
    meetings_completed: int
    total_savings_collected: Decimal
    total_loans_disbursed: Decimal
    total_loan_repaid: Decimal
    total_interest_collected: Decimal = Decimal("0")
    total_fines_collected: Decimal = Decimal("0")
    total_expenses: Decimal
    cash_in_hand_net: Decimal


class ExpenseLine(BaseModel):
    expense_type: str
    total: Decimal
    count: int


class ExpenseRow(BaseModel):
    expense_id: uuid.UUID
    meeting_id: uuid.UUID
    meeting_no: int
    meeting_date: date
    group_id: uuid.UUID
    group_name: str
    expense_type: str
    amount: Decimal


class ExpenseReport(BaseModel):
    """Org-wide expenses. The Expenses screen was a placeholder; expense
    rows only ever existed inside a single meeting's register, with no way
    to see what the organization actually spent over a period."""

    rows: list[ExpenseRow]
    by_type: list[ExpenseLine]
    total: Decimal
