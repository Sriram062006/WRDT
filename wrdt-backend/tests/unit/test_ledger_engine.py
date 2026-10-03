"""
Pure unit tests for the ledger engine -- the arithmetic behind every
rupee the system reports. No database, no HTTP: if these break, the
money is wrong everywhere.
"""
from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace

from app.services import ledger_engine


def entry(**kw):
    base = dict(
        present=True,
        prev_saving=Decimal("0"),
        cur_saving=Decimal("0"),
        loan_given=Decimal("0"),
        principal_paid=Decimal("0"),
        interest_paid=Decimal("0"),
        paid_till_date_opening=Decimal("0"),
        loan_remaining_opening=Decimal("0"),
        loan_remaining=Decimal("0"),
        loan_remaining_manual=False,
        fine=Decimal("0"),
        remarks="Paid",
    )
    base.update({k: Decimal(str(v)) if isinstance(v, (int, float, str)) and k not in
                 ("present", "loan_remaining_manual", "remarks") else v
                 for k, v in kw.items()})
    return SimpleNamespace(**base)


def expense(amount):
    return SimpleNamespace(amount=Decimal(str(amount)))


def test_row_cash_paid_is_savings_plus_principal_plus_fine_plus_interest():
    e = entry(cur_saving=300, principal_paid=1000, fine=50, interest_paid=120)
    assert ledger_engine.row_cash_paid(e) == Decimal("1470")


def test_row_cash_paid_excludes_loan_given():
    """A loan handed OUT is not cash the member paid in."""
    e = entry(cur_saving=300, loan_given=5000)
    assert ledger_engine.row_cash_paid(e) == Decimal("300")


def test_auto_loan_remaining_formula():
    e = entry(loan_remaining_opening=4000, loan_given=10000, principal_paid=2000)
    assert ledger_engine.auto_loan_remaining(e) == Decimal("12000")


def test_recalc_respects_a_manual_override():
    e = entry(loan_remaining_opening=4000, loan_given=1000, loan_remaining=Decimal("777"))
    e.loan_remaining_manual = True
    ledger_engine.recalc_loan_remaining_if_auto(e)
    assert e.loan_remaining == Decimal("777")

    e.loan_remaining_manual = False
    ledger_engine.recalc_loan_remaining_if_auto(e)
    assert e.loan_remaining == Decimal("5000")


def test_cash_in_hand_is_collected_minus_expenses_minus_loans():
    entries = [
        entry(cur_saving=300, principal_paid=1000, interest_paid=120, fine=50),
        entry(cur_saving=500, loan_given=5000),
    ]
    totals = ledger_engine.compute_totals(entries, [expense(500), expense(100)])

    assert totals.tot_savings == Decimal("800")
    assert totals.tot_cash_coll == Decimal("1970")
    assert totals.tot_expense == Decimal("600")
    assert totals.tot_loan == Decimal("5000")
    assert totals.cash_in_hand == Decimal("1970") - Decimal("600") - Decimal("5000")


def test_totals_of_an_empty_register_are_zero_not_an_error():
    totals = ledger_engine.compute_totals([], [])
    assert totals.tot_cash_coll == Decimal("0")
    assert totals.cash_in_hand == Decimal("0")
    assert totals.present == 0 and totals.absent == 0


def test_present_and_absent_counts():
    entries = [entry(), entry(), entry()]
    entries[2].present = False
    totals = ledger_engine.compute_totals(entries, [])
    assert totals.present == 2
    assert totals.absent == 1


def test_paid_till_date_accumulates_the_opening_plus_this_meeting():
    entries = [entry(paid_till_date_opening=1000, principal_paid=500)]
    assert ledger_engine.compute_totals(entries, []).tot_paid_till_date == Decimal("1500")


def test_total_saving_is_prev_plus_current():
    entries = [entry(prev_saving=4400, cur_saving=300), entry(prev_saving=5200, cur_saving=300)]
    totals = ledger_engine.compute_totals(entries, [])
    assert totals.tot_prev_saving == Decimal("9600")
    assert totals.tot_savings == Decimal("600")
    assert totals.tot_total_saving == Decimal("10200")


def test_decimal_arithmetic_has_no_float_drift():
    """Paise matter: 0.1 + 0.2 must be exactly 0.3, which float would
    not guarantee."""
    entries = [entry(cur_saving="0.10"), entry(cur_saving="0.20")]
    assert ledger_engine.compute_totals(entries, []).tot_savings == Decimal("0.30")
