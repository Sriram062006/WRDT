"""
Ledger Engine — the single source of truth for every derived ledger number,
ported 1:1 from the frontend's `ledgerTotals()` / row-level `rowCashPaid`
logic. NOTHING else in the backend is allowed to compute these numbers
independently (API responses, exports in a later phase, reports in a later
phase — all of them call into this module).

Deliberately pure / framework-free: no DB session, no FastAPI imports, so
it can be unit-tested against fixed input rows without touching a
database — this is the highest-risk code path in the whole system (real
money, real households), so it needs to be the easiest part to test in
isolation.

Row-level formula (mirrors the frontend):
    row_cash_paid = cur_saving + principal_paid + fine + interest_paid
    auto loan_remaining = loan_remaining_opening + loan_given - principal_paid
        (only while loan_remaining_manual is False; a manual override
        freezes loan_remaining at whatever value the supervisor entered)

Meeting-level totals (mirrors ledgerTotals()):
    tot_prev_saving      = sum(prev_saving)
    tot_savings          = sum(cur_saving)
    tot_total_saving     = tot_prev_saving + tot_savings
    tot_loan             = sum(loan_given)
    tot_paid_till_date   = sum(paid_till_date_opening + principal_paid)
    tot_install           = sum(principal_paid)
    tot_interest           = sum(interest_paid)
    tot_fine                = sum(fine)
    tot_expense               = sum(expense.amount)
    tot_cash_coll              = sum(row_cash_paid)
    cash_in_hand                 = tot_cash_coll - tot_expense - tot_loan
    loan_remaining (meeting tot) = sum(loan_remaining)
"""
from __future__ import annotations

from decimal import Decimal

from app.models.expense import Expense
from app.models.meeting_entry import MeetingEntry
from app.schemas.meeting_entry import LedgerTotals

ZERO = Decimal("0")


def row_cash_paid(entry: MeetingEntry) -> Decimal:
    return (
        Decimal(entry.cur_saving)
        + Decimal(entry.principal_paid)
        + Decimal(entry.fine)
        + Decimal(entry.interest_paid)
    )


def auto_loan_remaining(entry: MeetingEntry) -> Decimal:
    """The auto-calculated value — callers decide whether to apply it based
    on `entry.loan_remaining_manual`; this function never looks at the flag
    itself, keeping the "unless manual" branch explicit at the call site
    (meeting_service), exactly matching the frontend's own guard:
    `if((key==="loan"||key==="install") && !x.loanRemainingManual)`."""
    return (
        Decimal(entry.loan_remaining_opening)
        + Decimal(entry.loan_given)
        - Decimal(entry.principal_paid)
    )


def recalc_loan_remaining_if_auto(entry: MeetingEntry) -> None:
    """Mutates entry.loan_remaining in place, ONLY if not manually
    overridden. Called by meeting_service whenever loan_given or
    principal_paid changes on a draft entry."""
    if not entry.loan_remaining_manual:
        entry.loan_remaining = auto_loan_remaining(entry)


def compute_totals(entries: list[MeetingEntry], expenses: list[Expense]) -> LedgerTotals:
    tot_prev_saving = sum((Decimal(e.prev_saving) for e in entries), ZERO)
    tot_savings = sum((Decimal(e.cur_saving) for e in entries), ZERO)
    tot_loan = sum((Decimal(e.loan_given) for e in entries), ZERO)
    tot_paid_till_date = sum(
        (Decimal(e.paid_till_date_opening) + Decimal(e.principal_paid) for e in entries), ZERO
    )
    tot_install = sum((Decimal(e.principal_paid) for e in entries), ZERO)
    tot_interest = sum((Decimal(e.interest_paid) for e in entries), ZERO)
    tot_fine = sum((Decimal(e.fine) for e in entries), ZERO)
    tot_expense = sum((Decimal(x.amount) for x in expenses), ZERO)
    tot_cash_coll = sum((row_cash_paid(e) for e in entries), ZERO)
    tot_loan_remaining = sum((Decimal(e.loan_remaining) for e in entries), ZERO)

    cash_in_hand = tot_cash_coll - tot_expense - tot_loan

    present = sum(1 for e in entries if e.present)
    absent = sum(1 for e in entries if not e.present)

    return LedgerTotals(
        tot_prev_saving=tot_prev_saving,
        tot_savings=tot_savings,
        tot_total_saving=tot_prev_saving + tot_savings,
        tot_loan=tot_loan,
        tot_paid_till_date=tot_paid_till_date,
        tot_install=tot_install,
        tot_interest=tot_interest,
        tot_fine=tot_fine,
        tot_expense=tot_expense,
        tot_cash_coll=tot_cash_coll,
        cash_in_hand=cash_in_hand,
        loan_remaining=tot_loan_remaining,
        present=present,
        absent=absent,
    )
