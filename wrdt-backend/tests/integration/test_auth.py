"""Authentication, session termination and brute-force resistance."""
from __future__ import annotations

import pytest

from app.core.throttle import login_throttle
from tests.conftest import _make_org_and_owner, auth


@pytest.fixture(autouse=True)
def _reset_throttle():
    login_throttle.reset()
    yield
    login_throttle.reset()


async def test_login_returns_tokens_and_me_works(client, owner_ctx):
    resp = await client.get("/api/v1/auth/me", headers=owner_ctx["headers"])
    assert resp.status_code == 200
    body = resp.json()
    assert body["role"] == "owner"
    assert body["user"]["is_active"] is True


async def test_login_rejects_wrong_password(client, roles):
    await _make_org_and_owner("wp@wrdt.example.org", "WP Org")
    resp = await client.post(
        "/api/v1/auth/login", json={"email": "wp@wrdt.example.org", "password": "nope"}
    )
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "authentication_error"


async def test_unknown_email_and_wrong_password_are_indistinguishable(client, roles):
    await _make_org_and_owner("known@wrdt.example.org", "Known Org")
    wrong = await client.post(
        "/api/v1/auth/login", json={"email": "known@wrdt.example.org", "password": "bad"}
    )
    unknown = await client.post(
        "/api/v1/auth/login", json={"email": "ghost@wrdt.example.org", "password": "bad"}
    )
    # Identical status AND identical body: the endpoint must not be usable
    # to discover which email addresses have accounts.
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json()


async def test_protected_route_requires_token(client):
    assert (await client.get("/api/v1/regions")).status_code == 401


async def test_garbage_token_is_rejected(client):
    resp = await client.get("/api/v1/regions", headers=auth("not-a-jwt"))
    assert resp.status_code == 401


async def test_refresh_rotates_and_burns_the_old_token(client, roles):
    await _make_org_and_owner("rot@wrdt.example.org", "Rot Org")
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": "rot@wrdt.example.org", "password": "OwnerPass123!"},
    )
    old_refresh = login.json()["refresh_token"]

    first = await client.post("/api/v1/auth/refresh", json={"refresh_token": old_refresh})
    assert first.status_code == 200

    # Replaying the consumed refresh token must fail -- this is what makes
    # a leaked token single-use rather than valid for 14 days.
    replay = await client.post("/api/v1/auth/refresh", json={"refresh_token": old_refresh})
    assert replay.status_code == 401


async def test_logout_revokes_the_refresh_token(client, roles):
    await _make_org_and_owner("lo@wrdt.example.org", "LO Org")
    login = await client.post(
        "/api/v1/auth/login", json={"email": "lo@wrdt.example.org", "password": "OwnerPass123!"}
    )
    refresh = login.json()["refresh_token"]

    logout = await client.post("/api/v1/auth/logout", json={"refresh_token": refresh})
    assert logout.status_code == 204

    after = await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh})
    assert after.status_code == 401


async def test_logout_is_safe_to_call_with_no_body(client):
    assert (await client.post("/api/v1/auth/logout")).status_code == 204


async def test_repeated_failures_are_throttled(client, roles):
    await _make_org_and_owner("bf@wrdt.example.org", "BF Org")
    statuses = []
    for _ in range(12):
        r = await client.post(
            "/api/v1/auth/login",
            json={"email": "bf@wrdt.example.org", "password": "wrong"},
        )
        statuses.append(r.status_code)
    # An unbounded password oracle would return 401 every time.
    assert 429 in statuses


async def test_change_password_requires_the_current_one(client, owner_ctx):
    bad = await client.post(
        "/api/v1/auth/change-password",
        json={"current_password": "wrong", "new_password": "BrandNewPass123!"},
        headers=owner_ctx["headers"],
    )
    assert bad.status_code == 403

    good = await client.post(
        "/api/v1/auth/change-password",
        json={"current_password": "OwnerPass123!", "new_password": "BrandNewPass123!"},
        headers=owner_ctx["headers"],
    )
    assert good.status_code == 204


async def test_deactivated_user_loses_access_immediately(client, owner_ctx, db):
    from sqlalchemy import update

    from app.models.user import User

    await db.execute(
        update(User).where(User.id == owner_ctx["user_id"]).values(is_active=False)
    )
    await db.commit()

    # The token is still cryptographically valid; the server must re-read
    # the user's state rather than trusting the claims.
    resp = await client.get("/api/v1/regions", headers=owner_ctx["headers"])
    assert resp.status_code == 401
