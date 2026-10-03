"""
Cross-organization access control.

This is the regression suite for the most serious defect found in the
original code: every by-ID route fetched rows with a bare
`WHERE id = :id` and no organization predicate, so any authenticated
Owner could read and mutate any other tenant's regions, groups, members,
meetings and users by holding or guessing a UUID.

Each test drives two real organizations through the real HTTP stack and
asserts that org B cannot touch org A's data.
"""
from __future__ import annotations

import pytest

from tests.conftest import _login, _make_supervisor, auth


async def _seed_tree(client, ctx):
    """region -> group -> member -> started meeting, inside one org."""
    region = (
        await client.post("/api/v1/regions", json={"name": "Jagadevi"}, headers=ctx["headers"])
    ).json()
    group = (
        await client.post(
            f"/api/v1/regions/{region['id']}/groups",
            json={"name": "Lakshmi SHG"},
            headers=ctx["headers"],
        )
    ).json()
    member = (
        await client.post(
            f"/api/v1/groups/{group['id']}/members",
            json={"name": "R. Lakshmi", "seed_prev_saving": "4400"},
            headers=ctx["headers"],
        )
    ).json()
    meeting = (
        await client.post(
            f"/api/v1/groups/{group['id']}/meetings/start", headers=ctx["headers"]
        )
    ).json()
    return region, group, member, meeting


async def test_setup_is_sane(client, owner_ctx):
    region, group, member, meeting = await _seed_tree(client, owner_ctx)
    assert region["name"] == "Jagadevi"
    assert meeting["meeting_no"] == 1
    assert len(meeting["entries"]) == 1
    # `group` is the create-time snapshot, taken before the member
    # existed; re-read it to see the live count.
    fresh = (
        await client.get(f"/api/v1/groups/{group['id']}", headers=owner_ctx["headers"])
    ).json()
    assert fresh["members_count"] == 1


@pytest.mark.parametrize("method", ["get", "put", "delete"])
async def test_foreign_region_is_invisible(client, owner_ctx, other_org_ctx, method):
    region, *_ = await _seed_tree(client, owner_ctx)
    url = f"/api/v1/regions/{region['id']}"
    kwargs = {"headers": other_org_ctx["headers"]}
    if method == "put":
        kwargs["json"] = {"name": "Hijacked"}
    resp = await getattr(client, method)(url, **kwargs)
    assert resp.status_code == 404, f"{method} leaked a foreign region: {resp.text}"


@pytest.mark.parametrize("method", ["get", "put", "delete"])
async def test_foreign_group_is_invisible(client, owner_ctx, other_org_ctx, method):
    _, group, *_ = await _seed_tree(client, owner_ctx)
    url = f"/api/v1/groups/{group['id']}"
    kwargs = {"headers": other_org_ctx["headers"]}
    if method == "put":
        kwargs["json"] = {"name": "Hijacked"}
    resp = await getattr(client, method)(url, **kwargs)
    assert resp.status_code == 404


@pytest.mark.parametrize("method", ["get", "put", "delete"])
async def test_foreign_member_is_invisible(client, owner_ctx, other_org_ctx, method):
    _, _, member, _ = await _seed_tree(client, owner_ctx)
    url = f"/api/v1/members/{member['id']}"
    kwargs = {"headers": other_org_ctx["headers"]}
    if method == "put":
        kwargs["json"] = {"name": "Hijacked"}
    resp = await getattr(client, method)(url, **kwargs)
    assert resp.status_code == 404


async def test_foreign_meeting_cannot_be_read_or_written(client, owner_ctx, other_org_ctx):
    _, _, member, meeting = await _seed_tree(client, owner_ctx)
    h = other_org_ctx["headers"]

    assert (await client.get(f"/api/v1/meetings/{meeting['id']}", headers=h)).status_code == 404
    assert (
        await client.put(
            f"/api/v1/meetings/{meeting['id']}/entries/{member['id']}",
            json={"cur_saving": "999999"},
            headers=h,
        )
    ).status_code == 404
    assert (
        await client.post(
            f"/api/v1/meetings/{meeting['id']}/expenses",
            json={"expense_type": "Travel", "amount": "500"},
            headers=h,
        )
    ).status_code == 404
    assert (
        await client.post(f"/api/v1/meetings/{meeting['id']}/complete", headers=h)
    ).status_code == 404
    assert (
        await client.get(f"/api/v1/meetings/{meeting['id']}/export.xlsx", headers=h)
    ).status_code == 404


async def test_listing_never_shows_another_orgs_rows(client, owner_ctx, other_org_ctx):
    await _seed_tree(client, owner_ctx)
    for url in ("/api/v1/regions", "/api/v1/groups", "/api/v1/members"):
        body = (await client.get(url, headers=other_org_ctx["headers"])).json()
        assert body["total"] == 0, f"{url} leaked rows across tenants"
        assert body["items"] == []


async def test_nested_listing_under_a_foreign_region_404s(client, owner_ctx, other_org_ctx):
    region, *_ = await _seed_tree(client, owner_ctx)
    resp = await client.get(
        f"/api/v1/regions/{region['id']}/groups", headers=other_org_ctx["headers"]
    )
    assert resp.status_code == 404


async def test_foreign_user_cannot_be_read_or_modified(client, owner_ctx, other_org_ctx):
    victim = owner_ctx["user_id"]
    h = other_org_ctx["headers"]
    assert (await client.get(f"/api/v1/users/{victim}", headers=h)).status_code == 404
    assert (
        await client.put(f"/api/v1/users/{victim}", json={"is_active": False}, headers=h)
    ).status_code == 404
    assert (await client.delete(f"/api/v1/users/{victim}", headers=h)).status_code == 404


async def test_user_count_is_scoped_to_my_organization(client, owner_ctx, other_org_ctx):
    body = (await client.get("/api/v1/users", headers=owner_ctx["headers"])).json()
    # Two orgs with one Owner each exist; I must only be told about mine.
    assert body["total"] == 1


async def test_created_user_lands_in_my_org_not_a_supplied_one(client, owner_ctx, other_org_ctx):
    roles = (await client.get("/api/v1/users/roles", headers=owner_ctx["headers"])).json()
    supervisor_role = next(r for r in roles if r["name"] == "supervisor")
    resp = await client.post(
        "/api/v1/users",
        json={
            # A hostile client attempts to plant the account in another
            # tenant. organization_id is not part of the schema any more,
            # so it is ignored and the caller's own org is used.
            "organization_id": str(other_org_ctx["org_id"]),
            "role_id": supervisor_role["id"],
            "email": "planted@wrdt.example.org",
            "password": "PlantedPass123!",
            "full_name": "Planted",
        },
        headers=owner_ctx["headers"],
    )
    assert resp.status_code == 201
    assert resp.json()["organization_id"] == str(owner_ctx["org_id"])


async def test_supervisor_cannot_reach_unassigned_groups(client, owner_ctx):
    _, group, member, meeting = await _seed_tree(client, owner_ctx)
    await _make_supervisor(owner_ctx["org_id"], "sup@wrdt.example.org")
    token = await _login(client, "sup@wrdt.example.org", "SuperPass123!")
    h = auth(token)

    # Same organization, but no assignment -> 403, not data.
    assert (await client.get(f"/api/v1/groups/{group['id']}", headers=h)).status_code == 403
    assert (
        await client.get(f"/api/v1/groups/{group['id']}/members", headers=h)
    ).status_code == 403
    assert (await client.get(f"/api/v1/meetings/{meeting['id']}", headers=h)).status_code == 403
    assert (await client.get("/api/v1/groups", headers=h)).json()["total"] == 0


async def test_supervisor_can_reach_assigned_groups_only(client, owner_ctx):
    _, group, member, meeting = await _seed_tree(client, owner_ctx)
    sup_id = await _make_supervisor(owner_ctx["org_id"], "sup2@wrdt.example.org")
    assign = await client.post(
        "/api/v1/users/group-assignments",
        json={"user_id": str(sup_id), "group_id": group["id"]},
        headers=owner_ctx["headers"],
    )
    assert assign.status_code == 201

    token = await _login(client, "sup2@wrdt.example.org", "SuperPass123!")
    h = auth(token)
    assert (await client.get(f"/api/v1/groups/{group['id']}", headers=h)).status_code == 200
    assert (await client.get(f"/api/v1/meetings/{meeting['id']}", headers=h)).status_code == 200
    assert (await client.get("/api/v1/groups", headers=h)).json()["total"] == 1


async def test_supervisor_is_blocked_from_owner_only_areas(client, owner_ctx):
    _, group, *_ = await _seed_tree(client, owner_ctx)
    sup_id = await _make_supervisor(owner_ctx["org_id"], "sup3@wrdt.example.org")
    await client.post(
        "/api/v1/users/group-assignments",
        json={"user_id": str(sup_id), "group_id": group["id"]},
        headers=owner_ctx["headers"],
    )
    token = await _login(client, "sup3@wrdt.example.org", "SuperPass123!")
    h = auth(token)

    assert (await client.get("/api/v1/regions", headers=h)).status_code == 403
    assert (await client.get("/api/v1/users", headers=h)).status_code == 403
    assert (await client.get("/api/v1/reports/monthly?year=2026&month=1", headers=h)).status_code == 403
    assert (
        await client.post(
            f"/api/v1/regions/{group['region_id']}/groups", json={"name": "X"}, headers=h
        )
    ).status_code == 403


async def test_supervisor_group_assignment_across_orgs_is_refused(
    client, owner_ctx, other_org_ctx
):
    _, group, *_ = await _seed_tree(client, owner_ctx)
    foreign_sup = await _make_supervisor(other_org_ctx["org_id"], "fsup@wrdt.example.org")
    resp = await client.post(
        "/api/v1/users/group-assignments",
        json={"user_id": str(foreign_sup), "group_id": group["id"]},
        headers=owner_ctx["headers"],
    )
    assert resp.status_code == 404


async def test_last_owner_cannot_be_deactivated(client, owner_ctx):
    """An organization with zero active Owners is unrecoverable via the
    UI, so the API must refuse to create that state."""
    roles = (await client.get("/api/v1/users/roles", headers=owner_ctx["headers"])).json()
    sup_role = next(r for r in roles if r["name"] == "supervisor")
    second = (
        await client.post(
            "/api/v1/users",
            json={
                "role_id": sup_role["id"],
                "email": "second@wrdt.example.org",
                "password": "SecondPass123!",
                "full_name": "Second",
            },
            headers=owner_ctx["headers"],
        )
    ).json()

    # Self-deactivation is refused outright...
    assert (
        await client.delete(f"/api/v1/users/{owner_ctx['user_id']}", headers=owner_ctx["headers"])
    ).status_code == 422
    # ...and the non-owner can be removed without tripping the guard.
    assert (
        await client.delete(f"/api/v1/users/{second['id']}", headers=owner_ctx["headers"])
    ).status_code == 204
