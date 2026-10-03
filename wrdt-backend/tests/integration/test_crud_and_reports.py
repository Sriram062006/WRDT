"""CRUD rules, cascades, reports, and the Excel import round trip."""
from __future__ import annotations

import io
from decimal import Decimal

from openpyxl import Workbook


def D(x) -> Decimal:
    return Decimal(str(x))


async def _tree(client, ctx):
    region = (
        await client.post("/api/v1/regions", json={"name": "Krishnagiri"}, headers=ctx["headers"])
    ).json()
    group = (
        await client.post(
            f"/api/v1/regions/{region['id']}/groups",
            json={"name": "Parvathi SHG"},
            headers=ctx["headers"],
        )
    ).json()
    return region, group


# -- naming rules ---------------------------------------------------------
async def test_duplicate_region_name_is_rejected_case_insensitively(client, owner_ctx):
    h = owner_ctx["headers"]
    assert (await client.post("/api/v1/regions", json={"name": "Bargur"}, headers=h)).status_code == 201
    dup = await client.post("/api/v1/regions", json={"name": "  bargur "}, headers=h)
    assert dup.status_code == 409


async def test_same_group_name_allowed_in_different_regions(client, owner_ctx):
    h = owner_ctx["headers"]
    r1 = (await client.post("/api/v1/regions", json={"name": "R1"}, headers=h)).json()
    r2 = (await client.post("/api/v1/regions", json={"name": "R2"}, headers=h)).json()
    assert (
        await client.post(f"/api/v1/regions/{r1['id']}/groups", json={"name": "Lakshmi SHG"}, headers=h)
    ).status_code == 201
    # Group names are unique per region, not globally.
    assert (
        await client.post(f"/api/v1/regions/{r2['id']}/groups", json={"name": "Lakshmi SHG"}, headers=h)
    ).status_code == 201


async def test_duplicate_member_in_same_group_is_rejected(client, owner_ctx):
    h = owner_ctx["headers"]
    _, group = await _tree(client, owner_ctx)
    assert (
        await client.post(f"/api/v1/groups/{group['id']}/members", json={"name": "Meena"}, headers=h)
    ).status_code == 201
    assert (
        await client.post(f"/api/v1/groups/{group['id']}/members", json={"name": "MEENA"}, headers=h)
    ).status_code == 409


async def test_member_codes_are_sequential(client, owner_ctx):
    h = owner_ctx["headers"]
    _, group = await _tree(client, owner_ctx)
    codes = []
    for name in ("Amutha", "Kavitha", "Divya"):
        codes.append(
            (
                await client.post(
                    f"/api/v1/groups/{group['id']}/members", json={"name": name}, headers=h
                )
            ).json()["code"]
        )
    assert codes == ["PS001", "PS002", "PS003"]


async def test_deleting_a_region_cascades_to_groups_and_members(client, owner_ctx):
    h = owner_ctx["headers"]
    region, group = await _tree(client, owner_ctx)
    await client.post(f"/api/v1/groups/{group['id']}/members", json={"name": "Vasanthi"}, headers=h)

    assert (await client.delete(f"/api/v1/regions/{region['id']}", headers=h)).status_code == 204
    assert (await client.get("/api/v1/regions", headers=h)).json()["total"] == 0
    assert (await client.get("/api/v1/groups", headers=h)).json()["total"] == 0
    assert (await client.get("/api/v1/members", headers=h)).json()["total"] == 0


async def test_region_counts_reflect_reality(client, owner_ctx):
    h = owner_ctx["headers"]
    region, group = await _tree(client, owner_ctx)
    for name in ("A", "B", "C"):
        await client.post(f"/api/v1/groups/{group['id']}/members", json={"name": name}, headers=h)
    fresh = (await client.get(f"/api/v1/regions/{region['id']}", headers=h)).json()
    assert fresh["groups_count"] == 1
    assert fresh["members_count"] == 3


async def test_member_search_matches_name_or_code(client, owner_ctx):
    h = owner_ctx["headers"]
    _, group = await _tree(client, owner_ctx)
    await client.post(f"/api/v1/groups/{group['id']}/members", json={"name": "Lalitha"}, headers=h)
    assert (await client.get("/api/v1/members?q=lalit", headers=h)).json()["total"] == 1
    assert (await client.get("/api/v1/members?q=PS001", headers=h)).json()["total"] == 1
    assert (await client.get("/api/v1/members?q=zzzz", headers=h)).json()["total"] == 0


# -- reports --------------------------------------------------------------
async def test_dashboard_reflects_real_data(client, owner_ctx):
    h = owner_ctx["headers"]
    _, group = await _tree(client, owner_ctx)
    m = (
        await client.post(
            f"/api/v1/groups/{group['id']}/members",
            json={"name": "Nandhini", "seed_prev_saving": "1000"},
            headers=h,
        )
    ).json()
    meeting = (
        await client.post(f"/api/v1/groups/{group['id']}/meetings/start", headers=h)
    ).json()
    await client.put(
        f"/api/v1/meetings/{meeting['id']}/entries/{m['id']}",
        json={"cur_saving": "300", "loan_given": "5000"},
        headers=h,
    )

    stats = (await client.get("/api/v1/reports/dashboard", headers=h)).json()
    assert stats["total_regions"] == 1
    assert stats["total_groups"] == 1
    assert stats["total_members"] == 1
    assert stats["active_meetings"] == 1
    assert D(stats["total_savings"]) == D(1300)
    assert D(stats["total_loans_outstanding"]) == D(5000)


async def test_outstanding_loans_are_not_multiplied_across_meetings(client, owner_ctx):
    """Regression: the dashboard summed `loan_remaining` over every
    historical entry, so one 5,000 loan looked like 15,000 after three
    meetings."""
    h = owner_ctx["headers"]
    _, group = await _tree(client, owner_ctx)
    m = (
        await client.post(f"/api/v1/groups/{group['id']}/members", json={"name": "Selvi"}, headers=h)
    ).json()

    first = (await client.post(f"/api/v1/groups/{group['id']}/meetings/start", headers=h)).json()
    await client.put(
        f"/api/v1/meetings/{first['id']}/entries/{m['id']}",
        json={"loan_given": "5000"},
        headers=h,
    )
    await client.post(f"/api/v1/meetings/{first['id']}/complete", headers=h)

    for _ in range(2):
        nxt = (await client.post(f"/api/v1/groups/{group['id']}/meetings/start", headers=h)).json()
        await client.post(f"/api/v1/meetings/{nxt['id']}/complete", headers=h)

    stats = (await client.get("/api/v1/reports/dashboard", headers=h)).json()
    assert D(stats["total_loans_outstanding"]) == D(5000)

    ledger = (await client.get("/api/v1/reports/loans", headers=h)).json()
    assert D(ledger["total_outstanding"]) == D(5000)
    assert len(ledger["entries"]) == 1


async def test_member_ledger_lists_every_meeting(client, owner_ctx):
    h = owner_ctx["headers"]
    _, group = await _tree(client, owner_ctx)
    m = (
        await client.post(
            f"/api/v1/groups/{group['id']}/members",
            json={"name": "Malar", "seed_prev_saving": "500"},
            headers=h,
        )
    ).json()
    first = (await client.post(f"/api/v1/groups/{group['id']}/meetings/start", headers=h)).json()
    await client.post(f"/api/v1/meetings/{first['id']}/complete", headers=h)
    await client.post(f"/api/v1/groups/{group['id']}/meetings/start", headers=h)

    report = (await client.get(f"/api/v1/reports/members/{m['id']}/ledger", headers=h)).json()
    assert len(report["rows"]) == 2
    assert D(report["current_savings_balance"]) == D(1100)   # 500 + 300 + 300


async def test_expense_report_aggregates_by_type(client, owner_ctx):
    h = owner_ctx["headers"]
    _, group = await _tree(client, owner_ctx)
    await client.post(f"/api/v1/groups/{group['id']}/members", json={"name": "X"}, headers=h)
    meeting = (await client.post(f"/api/v1/groups/{group['id']}/meetings/start", headers=h)).json()
    for t, a in (("Travel", "500"), ("Tea", "100"), ("Travel", "250")):
        await client.post(
            f"/api/v1/meetings/{meeting['id']}/expenses",
            json={"expense_type": t, "amount": a},
            headers=h,
        )

    report = (await client.get("/api/v1/reports/expenses", headers=h)).json()
    assert D(report["total"]) == D(850)
    travel = next(line for line in report["by_type"] if line["expense_type"] == "Travel")
    assert D(travel["total"]) == D(750) and travel["count"] == 2


async def test_activity_feed_records_real_actions(client, owner_ctx):
    h = owner_ctx["headers"]
    await _tree(client, owner_ctx)
    feed = (await client.get("/api/v1/reports/activity", headers=h)).json()
    actions = {i["action"] for i in feed["items"]}
    assert "region.create" in actions
    assert "group.create" in actions


async def test_collection_series_returns_real_points(client, owner_ctx):
    h = owner_ctx["headers"]
    _, group = await _tree(client, owner_ctx)
    m = (
        await client.post(f"/api/v1/groups/{group['id']}/members", json={"name": "Y"}, headers=h)
    ).json()
    meeting = (await client.post(f"/api/v1/groups/{group['id']}/meetings/start", headers=h)).json()
    await client.put(
        f"/api/v1/meetings/{meeting['id']}/entries/{m['id']}",
        json={"cur_saving": "300", "fine": "50"},
        headers=h,
    )
    series = (await client.get("/api/v1/reports/collections", headers=h)).json()
    assert len(series) == 1
    assert series[0]["amount"] == 350.0


# -- Excel import ---------------------------------------------------------
def _workbook(rows, headers=("Region", "Group", "Member Name", "Previous Savings")):
    wb = Workbook()
    ws = wb.active
    ws.append(list(headers))
    for r in rows:
        ws.append(list(r))
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf.read()


async def test_import_preview_then_commit(client, owner_ctx):
    h = owner_ctx["headers"]
    content = _workbook(
        [
            ("Jagadevi", "Lakshmi SHG", "R. Lakshmi", 4400),
            ("Jagadevi", "Lakshmi SHG", "R. Selvi", 5200),
            ("Jagadevi", "Durga SHG", "P. Priya", "1,250"),
        ]
    )
    files = {
        "file": (
            "import.xlsx",
            content,
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    }
    preview = await client.post("/api/v1/import/preview", files=files, headers=h)
    assert preview.status_code == 200, preview.text
    body = preview.json()
    assert body["summary"]["members_created"] == 3
    assert body["summary"]["invalid_rows"] == 0

    # Preview must be a dry run.
    assert (await client.get("/api/v1/regions", headers=h)).json()["total"] == 0

    commit = await client.post(f"/api/v1/import/{body['batch_id']}/commit", headers=h)
    assert commit.status_code == 201, commit.text
    assert (await client.get("/api/v1/regions", headers=h)).json()["total"] == 1
    assert (await client.get("/api/v1/groups", headers=h)).json()["total"] == 2
    assert (await client.get("/api/v1/members", headers=h)).json()["total"] == 3

    # "1,250" must survive Excel's comma formatting.
    members = (await client.get("/api/v1/members?q=Priya", headers=h)).json()["items"]
    assert D(members[0]["seed_prev_saving"]) == D(1250)


async def test_import_accepts_the_member_column_alias(client, owner_ctx):
    """The frontend template says 'Member Name'; the parser only accepted
    'Member', so every export from the UI was rejected."""
    h = owner_ctx["headers"]
    content = _workbook([("R", "G", "Someone", 0)], headers=("Region", "Group", "Member", "Previous Saving"))
    files = {"file": ("a.xlsx", content, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
    assert (await client.post("/api/v1/import/preview", files=files, headers=h)).status_code == 200


async def test_import_rejects_a_missing_column(client, owner_ctx):
    h = owner_ctx["headers"]
    content = _workbook([("R", "G")], headers=("Region", "Group"))
    files = {"file": ("a.xlsx", content, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
    resp = await client.post("/api/v1/import/preview", files=files, headers=h)
    assert resp.status_code == 422
    assert "Member Name" in resp.json()["error"]["message"]


async def test_import_flags_invalid_rows_without_aborting(client, owner_ctx):
    h = owner_ctx["headers"]
    content = _workbook([("Jagadevi", "G1", "Good", 100), ("", "G1", "NoRegion", 100)])
    files = {"file": ("a.xlsx", content, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
    body = (await client.post("/api/v1/import/preview", files=files, headers=h)).json()
    assert body["summary"]["invalid_rows"] == 1
    assert body["summary"]["members_created"] == 1


async def test_import_batch_cannot_be_committed_twice(client, owner_ctx):
    h = owner_ctx["headers"]
    content = _workbook([("R", "G", "Once", 0)])
    files = {"file": ("a.xlsx", content, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
    batch = (await client.post("/api/v1/import/preview", files=files, headers=h)).json()["batch_id"]
    assert (await client.post(f"/api/v1/import/{batch}/commit", headers=h)).status_code == 201
    assert (await client.post(f"/api/v1/import/{batch}/commit", headers=h)).status_code == 422


async def test_import_batch_is_not_committable_by_another_tenant(
    client, owner_ctx, other_org_ctx
):
    content = _workbook([("R", "G", "Victim", 0)])
    files = {"file": ("a.xlsx", content, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
    batch = (
        await client.post("/api/v1/import/preview", files=files, headers=owner_ctx["headers"])
    ).json()["batch_id"]
    resp = await client.post(
        f"/api/v1/import/{batch}/commit", headers=other_org_ctx["headers"]
    )
    assert resp.status_code == 404


async def test_import_template_downloads(client, owner_ctx):
    resp = await client.get("/api/v1/import/template.xlsx", headers=owner_ctx["headers"])
    assert resp.status_code == 200
    assert resp.content[:2] == b"PK"


async def test_import_rejects_non_excel(client, owner_ctx):
    files = {"file": ("notes.txt", b"hello", "text/plain")}
    resp = await client.post("/api/v1/import/preview", files=files, headers=owner_ctx["headers"])
    assert resp.status_code == 422
