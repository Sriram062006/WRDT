"""What deleting a member/group/region does to meeting history.

The UI promises that completed meetings are kept. These tests hold the
backend to that promise.
"""
from __future__ import annotations

from sqlalchemy import text


async def _setup(client, h):
    region = (await client.post("/api/v1/regions", json={"name": "R"}, headers=h)).json()
    group = (await client.post(f"/api/v1/regions/{region['id']}/groups", json={"name": "G"}, headers=h)).json()
    m = (await client.post(f"/api/v1/groups/{group['id']}/members", json={"name": "Gone", "seed_prev_saving": "100"}, headers=h)).json()
    m1 = (await client.post(f"/api/v1/groups/{group['id']}/meetings/start", headers=h)).json()
    await client.post(f"/api/v1/meetings/{m1['id']}/complete", headers=h)
    m2 = (await client.post(f"/api/v1/groups/{group['id']}/meetings/start", headers=h)).json()
    return region, group, m, m1, m2


async def _entries(db, meeting_id):
    return (await db.execute(text("SELECT count(*) FROM meeting_entries WHERE meeting_id=:m"), {"m": meeting_id})).scalar_one()


async def test_deleting_a_member_keeps_completed_history_and_leaves_the_open_register(client, owner_ctx, db):
    h = owner_ctx["headers"]
    _, _, m, m1, m2 = await _setup(client, h)
    assert (await client.delete(f"/api/v1/members/{m['id']}", headers=h)).status_code == 204
    assert await _entries(db, m1["id"]) == 1        # completed history intact
    open_reg = (await client.get(f"/api/v1/meetings/{m2['id']}", headers=h)).json()
    assert open_reg["entries"] == []                # removed from the open register


async def test_deleting_a_group_keeps_completed_meetings(client, owner_ctx, db):
    h = owner_ctx["headers"]
    _, group, _, m1, _ = await _setup(client, h)
    assert (await client.delete(f"/api/v1/groups/{group['id']}", headers=h)).status_code == 204
    assert await _entries(db, m1["id"]) == 1


async def test_deleting_a_region_keeps_completed_meetings(client, owner_ctx, db):
    h = owner_ctx["headers"]
    region, _, _, m1, _ = await _setup(client, h)
    assert (await client.delete(f"/api/v1/regions/{region['id']}", headers=h)).status_code == 204
    assert await _entries(db, m1["id"]) == 1
