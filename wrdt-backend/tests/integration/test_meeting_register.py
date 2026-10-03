"""
The WRDT Meeting Register: savings, loans, installments, interest, fines,
expenses, cash-in-hand, completion/locking and week-to-week carry-forward.

This is the money path. Every assertion below is written against the
paper-register rules the system is modelling, not against whatever the
code happens to do.
"""
from __future__ import annotations

from decimal import Decimal

import pytest


def D(x) -> Decimal:
    return Decimal(str(x))


async def _group_with_members(client, ctx, names, savings=None):
    region = (
        await client.post("/api/v1/regions", json={"name": "Bargur"}, headers=ctx["headers"])
    ).json()
    group = (
        await client.post(
            f"/api/v1/regions/{region['id']}/groups",
            json={"name": "Kamakshi SHG"},
            headers=ctx["headers"],
        )
    ).json()
    members = []
    for i, name in enumerate(names):
        seed = (savings or {}).get(name, 0)
        m = await client.post(
            f"/api/v1/groups/{group['id']}/members",
            json={"name": name, "seed_prev_saving": str(seed)},
            headers=ctx["headers"],
        )
        assert m.status_code == 201, m.text
        members.append(m.json())
    return region, group, members


async def _start(client, ctx, group_id):
    r = await client.post(f"/api/v1/groups/{group_id}/meetings/start", headers=ctx["headers"])
    assert r.status_code == 201, r.text
    return r.json()


async def test_first_meeting_seeds_opening_balances(client, owner_ctx):
    _, group, members = await _group_with_members(
        client, owner_ctx, ["A", "B"], {"A": 4400, "B": 5200}
    )
    meeting = await _start(client, owner_ctx, group["id"])
    by_member = {e["member_id"]: e for e in meeting["entries"]}

    a = by_member[members[0]["id"]]
    assert D(a["prev_saving"]) == D(4400)
    assert D(a["cur_saving"]) == D(300)      # DEFAULT_CURRENT_SAVING
    assert D(a["loan_given"]) == D(0)
    # Regression: the service used to pre-fill principal_paid from the
    # member's seed_install, charging a brand-new member for a repayment
    # they never made.
    assert D(a["principal_paid"]) == D(0)
    assert a["present"] is True


async def test_row_cash_paid_and_totals_match_the_register_formula(client, owner_ctx):
    _, group, members = await _group_with_members(client, owner_ctx, ["A", "B"], {"A": 1000, "B": 2000})
    meeting = await _start(client, owner_ctx, group["id"])
    mid = meeting["id"]
    h = owner_ctx["headers"]

    # A: saves 300, repays 1000 principal + 120 interest, fined 50
    await client.put(
        f"/api/v1/meetings/{mid}/entries/{members[0]['id']}",
        json={"cur_saving": "300", "principal_paid": "1000", "interest_paid": "120", "fine": "50"},
        headers=h,
    )
    # B: saves 500, takes a 5000 loan
    await client.put(
        f"/api/v1/meetings/{mid}/entries/{members[1]['id']}",
        json={"cur_saving": "500", "loan_given": "5000"},
        headers=h,
    )
    await client.post(
        f"/api/v1/meetings/{mid}/expenses",
        json={"expense_type": "Travel", "amount": "500"},
        headers=h,
    )

    detail = (await client.get(f"/api/v1/meetings/{mid}", headers=h)).json()
    t = detail["totals"]

    assert D(t["tot_savings"]) == D(800)                  # 300 + 500
    assert D(t["tot_prev_saving"]) == D(3000)             # 1000 + 2000
    assert D(t["tot_total_saving"]) == D(3800)
    assert D(t["tot_install"]) == D(1000)
    assert D(t["tot_interest"]) == D(120)
    assert D(t["tot_fine"]) == D(50)
    assert D(t["tot_loan"]) == D(5000)
    assert D(t["tot_expense"]) == D(500)
    # cash collected = savings + principal + fine + interest
    assert D(t["tot_cash_coll"]) == D(1970)
    # cash in hand = collected - expenses - loans paid out
    assert D(t["cash_in_hand"]) == D(1970) - D(500) - D(5000)
    assert t["present"] == 2 and t["absent"] == 0


async def test_loan_remaining_auto_recalculates(client, owner_ctx):
    _, group, members = await _group_with_members(client, owner_ctx, ["A"], {"A": 0})
    meeting = await _start(client, owner_ctx, group["id"])
    mid, member_id = meeting["id"], members[0]["id"]
    h = owner_ctx["headers"]

    entry = (
        await client.put(
            f"/api/v1/meetings/{mid}/entries/{member_id}",
            json={"loan_given": "10000", "principal_paid": "2000"},
            headers=h,
        )
    ).json()
    # opening(0) + given(10000) - repaid(2000)
    assert D(entry["loan_remaining"]) == D(8000)
    assert entry["loan_remaining_manual"] is False


async def test_manual_loan_override_freezes_then_resets(client, owner_ctx):
    _, group, members = await _group_with_members(client, owner_ctx, ["A"], {"A": 0})
    meeting = await _start(client, owner_ctx, group["id"])
    mid, member_id = meeting["id"], members[0]["id"]
    h = owner_ctx["headers"]

    await client.put(
        f"/api/v1/meetings/{mid}/entries/{member_id}",
        json={"loan_given": "10000", "principal_paid": "2000"},
        headers=h,
    )
    overridden = (
        await client.patch(
            f"/api/v1/meetings/{mid}/entries/{member_id}/loan-override",
            json={"loan_remaining": "7500"},
            headers=h,
        )
    ).json()
    assert D(overridden["loan_remaining"]) == D(7500)
    assert overridden["loan_remaining_manual"] is True

    # A later edit must NOT clobber the supervisor's manual correction.
    after_edit = (
        await client.put(
            f"/api/v1/meetings/{mid}/entries/{member_id}",
            json={"principal_paid": "3000"},
            headers=h,
        )
    ).json()
    assert D(after_edit["loan_remaining"]) == D(7500)

    reset = (
        await client.delete(
            f"/api/v1/meetings/{mid}/entries/{member_id}/loan-override", headers=h
        )
    ).json()
    assert reset["loan_remaining_manual"] is False
    assert D(reset["loan_remaining"]) == D(7000)   # 0 + 10000 - 3000


async def test_carry_forward_into_the_next_meeting(client, owner_ctx):
    _, group, members = await _group_with_members(client, owner_ctx, ["A"], {"A": 4400})
    m1 = await _start(client, owner_ctx, group["id"])
    mid1, member_id = m1["id"], members[0]["id"]
    h = owner_ctx["headers"]

    await client.put(
        f"/api/v1/meetings/{mid1}/entries/{member_id}",
        json={"cur_saving": "300", "loan_given": "5000", "principal_paid": "1000"},
        headers=h,
    )
    assert (await client.post(f"/api/v1/meetings/{mid1}/complete", headers=h)).status_code == 200

    m2 = await _start(client, owner_ctx, group["id"])
    e2 = m2["entries"][0]

    assert m2["meeting_no"] == 2
    # prev_saving = prior prev + prior current
    assert D(e2["prev_saving"]) == D(4700)
    # opening loan = prior closing balance (0 + 5000 - 1000)
    assert D(e2["loan_remaining_opening"]) == D(4000)
    assert D(e2["loan_remaining"]) == D(4000)
    # cumulative principal repaid before this meeting
    assert D(e2["paid_till_date_opening"]) == D(1000)
    # this meeting's own loan/repayment columns start blank
    assert D(e2["loan_given"]) == D(0)
    assert D(e2["principal_paid"]) == D(0)


async def test_meeting_date_advances_by_the_fortnightly_interval(client, owner_ctx):
    from datetime import date, timedelta

    _, group, _ = await _group_with_members(client, owner_ctx, ["A"])
    m1 = await _start(client, owner_ctx, group["id"])
    await client.post(f"/api/v1/meetings/{m1['id']}/complete", headers=owner_ctx["headers"])
    m2 = await _start(client, owner_ctx, group["id"])
    d1 = date.fromisoformat(m1["meeting_date"])
    d2 = date.fromisoformat(m2["meeting_date"])
    assert d2 - d1 == timedelta(days=15)


async def test_completed_meeting_is_permanently_locked(client, owner_ctx):
    _, group, members = await _group_with_members(client, owner_ctx, ["A"])
    meeting = await _start(client, owner_ctx, group["id"])
    mid, member_id = meeting["id"], members[0]["id"]
    h = owner_ctx["headers"]

    expense = (
        await client.post(
            f"/api/v1/meetings/{mid}/expenses",
            json={"expense_type": "Tea", "amount": "100"},
            headers=h,
        )
    ).json()

    completed = (await client.post(f"/api/v1/meetings/{mid}/complete", headers=h)).json()
    assert completed["status"] == "completed"
    assert completed["locked"] is True
    assert completed["completed_at"] is not None

    # Every mutating path must now refuse with a clean 409.
    assert (
        await client.put(
            f"/api/v1/meetings/{mid}/entries/{member_id}",
            json={"cur_saving": "9999"},
            headers=h,
        )
    ).status_code == 409
    assert (
        await client.put(
            f"/api/v1/meetings/{mid}/entries",
            json={"entries": [{"member_id": member_id, "cur_saving": "9999"}]},
            headers=h,
        )
    ).status_code == 409
    assert (
        await client.patch(
            f"/api/v1/meetings/{mid}/entries/{member_id}/loan-override",
            json={"loan_remaining": "1"},
            headers=h,
        )
    ).status_code == 409
    assert (
        await client.post(
            f"/api/v1/meetings/{mid}/expenses",
            json={"expense_type": "X", "amount": "1"},
            headers=h,
        )
    ).status_code == 409
    assert (
        await client.delete(f"/api/v1/meetings/{mid}/expenses/{expense['id']}", headers=h)
    ).status_code == 409


async def test_database_trigger_blocks_writes_even_bypassing_the_service(client, owner_ctx, db):
    """The service-layer lock check is a nicety; the database trigger is
    the actual guarantee. This writes straight to the table to prove the
    guarantee holds without the application's cooperation.

    It also covers the DELETE branch, which previously raised
    `record "new" is not assigned yet` instead of enforcing the lock."""
    from sqlalchemy import text
    from sqlalchemy.exc import DBAPIError

    _, group, members = await _group_with_members(client, owner_ctx, ["A"])
    meeting = await _start(client, owner_ctx, group["id"])
    mid = meeting["id"]
    await client.post(f"/api/v1/meetings/{mid}/complete", headers=owner_ctx["headers"])

    with pytest.raises(DBAPIError):
        await db.execute(
            text("UPDATE meeting_entries SET cur_saving = 99999 WHERE meeting_id = :m"),
            {"m": mid},
        )
    await db.rollback()

    with pytest.raises(DBAPIError):
        await db.execute(
            text("DELETE FROM meeting_entries WHERE meeting_id = :m"), {"m": mid}
        )
    await db.rollback()


async def test_a_completed_meeting_cannot_be_reopened(client, owner_ctx, db):
    from sqlalchemy import text
    from sqlalchemy.exc import DBAPIError

    _, group, _ = await _group_with_members(client, owner_ctx, ["A"])
    meeting = await _start(client, owner_ctx, group["id"])
    await client.post(f"/api/v1/meetings/{meeting['id']}/complete", headers=owner_ctx["headers"])

    with pytest.raises(DBAPIError):
        await db.execute(
            text("UPDATE meetings SET locked = FALSE WHERE id = :m"), {"m": meeting["id"]}
        )
    await db.rollback()


async def test_only_one_open_meeting_per_group(client, owner_ctx):
    _, group, _ = await _group_with_members(client, owner_ctx, ["A"])
    first = await _start(client, owner_ctx, group["id"])
    # Starting again while one is open resumes it rather than opening a
    # second register page for the same group.
    second = await _start(client, owner_ctx, group["id"])
    assert second["id"] == first["id"]
    assert second["meeting_no"] == first["meeting_no"]


async def test_completing_twice_is_idempotent(client, owner_ctx):
    _, group, _ = await _group_with_members(client, owner_ctx, ["A"])
    meeting = await _start(client, owner_ctx, group["id"])
    h = owner_ctx["headers"]
    assert (await client.post(f"/api/v1/meetings/{meeting['id']}/complete", headers=h)).status_code == 200
    assert (await client.post(f"/api/v1/meetings/{meeting['id']}/complete", headers=h)).status_code == 200


async def test_bulk_save_applies_the_whole_sheet_atomically(client, owner_ctx):
    _, group, members = await _group_with_members(client, owner_ctx, ["A", "B", "C"])
    meeting = await _start(client, owner_ctx, group["id"])
    mid = meeting["id"]
    h = owner_ctx["headers"]

    resp = await client.put(
        f"/api/v1/meetings/{mid}/entries",
        json={"entries": [{"member_id": m["id"], "cur_saving": "500"} for m in members]},
        headers=h,
    )
    assert resp.status_code == 200
    assert D(resp.json()["totals"]["tot_savings"]) == D(1500)


async def test_bulk_save_rolls_back_entirely_on_a_bad_row(client, owner_ctx):
    import uuid as _uuid

    _, group, members = await _group_with_members(client, owner_ctx, ["A", "B"])
    meeting = await _start(client, owner_ctx, group["id"])
    mid = meeting["id"]
    h = owner_ctx["headers"]

    resp = await client.put(
        f"/api/v1/meetings/{mid}/entries",
        json={
            "entries": [
                {"member_id": members[0]["id"], "cur_saving": "700"},
                {"member_id": str(_uuid.uuid4()), "cur_saving": "700"},  # not in this meeting
            ]
        },
        headers=h,
    )
    assert resp.status_code == 404

    # The valid row must NOT have been persisted -- a half-saved register
    # is worse than an unsaved one.
    detail = (await client.get(f"/api/v1/meetings/{mid}", headers=h)).json()
    assert D(detail["totals"]["tot_savings"]) == D(600)   # 2 x default 300


async def test_negative_money_is_rejected(client, owner_ctx):
    _, group, members = await _group_with_members(client, owner_ctx, ["A"])
    meeting = await _start(client, owner_ctx, group["id"])
    h = owner_ctx["headers"]
    for field in ("cur_saving", "loan_given", "principal_paid", "interest_paid", "fine"):
        resp = await client.put(
            f"/api/v1/meetings/{meeting['id']}/entries/{members[0]['id']}",
            json={field: "-100"},
            headers=h,
        )
        assert resp.status_code == 422, f"{field} accepted a negative amount"


async def test_absent_member_still_carries_their_balance_forward(client, owner_ctx):
    _, group, members = await _group_with_members(client, owner_ctx, ["A"], {"A": 4400})
    m1 = await _start(client, owner_ctx, group["id"])
    h = owner_ctx["headers"]
    await client.put(
        f"/api/v1/meetings/{m1['id']}/entries/{members[0]['id']}",
        json={"present": False, "cur_saving": "0", "remarks": "Absent"},
        headers=h,
    )
    await client.post(f"/api/v1/meetings/{m1['id']}/complete", headers=h)

    m2 = await _start(client, owner_ctx, group["id"])
    # She saved nothing, so her balance is unchanged -- but it must not
    # vanish just because she missed a week.
    assert D(m2["entries"][0]["prev_saving"]) == D(4400)


async def test_new_member_joins_the_open_register_immediately(client, owner_ctx):
    _, group, _ = await _group_with_members(client, owner_ctx, ["A"])
    meeting = await _start(client, owner_ctx, group["id"])
    h = owner_ctx["headers"]

    await client.post(
        f"/api/v1/groups/{group['id']}/members",
        json={"name": "Latecomer", "seed_prev_saving": "100"},
        headers=h,
    )
    detail = (await client.get(f"/api/v1/meetings/{meeting['id']}", headers=h)).json()
    assert len(detail["entries"]) == 2


async def test_meeting_list_totals_match_the_register(client, owner_ctx):
    _, group, members = await _group_with_members(client, owner_ctx, ["A", "B"])
    meeting = await _start(client, owner_ctx, group["id"])
    mid = meeting["id"]
    h = owner_ctx["headers"]

    await client.put(
        f"/api/v1/meetings/{mid}/entries/{members[0]['id']}",
        json={"cur_saving": "300", "principal_paid": "200", "fine": "50", "interest_paid": "25"},
        headers=h,
    )
    await client.put(
        f"/api/v1/meetings/{mid}/entries/{members[1]['id']}",
        json={"cur_saving": "300", "loan_given": "1000"},
        headers=h,
    )
    await client.post(
        f"/api/v1/meetings/{mid}/expenses", json={"expense_type": "Tea", "amount": "100"}, headers=h
    )

    detail = (await client.get(f"/api/v1/meetings/{mid}", headers=h)).json()["totals"]
    row = (await client.get(f"/api/v1/groups/{group['id']}/meetings", headers=h)).json()["items"][0]

    # The list view aggregates in SQL while the register uses the Python
    # ledger engine; if these two ever disagree the UI shows one number on
    # the list and a different one after the user clicks in.
    assert D(row["total_saving"]) == D(detail["tot_savings"])
    assert D(row["total_loan"]) == D(detail["tot_loan"])
    assert D(row["total_expense"]) == D(detail["tot_expense"])
    assert D(row["cash_in_hand"]) == D(detail["cash_in_hand"])
    assert row["members_present"] == detail["present"]


async def test_excel_export_of_a_register(client, owner_ctx):
    _, group, _ = await _group_with_members(client, owner_ctx, ["A"])
    meeting = await _start(client, owner_ctx, group["id"])
    resp = await client.get(
        f"/api/v1/meetings/{meeting['id']}/export.xlsx", headers=owner_ctx["headers"]
    )
    assert resp.status_code == 200
    assert resp.content[:2] == b"PK"      # a real xlsx (zip) payload
    assert "attachment" in resp.headers["content-disposition"]
