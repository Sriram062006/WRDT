from __future__ import annotations


async def test_security_headers_are_present_on_every_response(client):
    for path in ("/api/v1/health", "/api/v1/regions"):  # one OK, one 401
        h = (await client.get(path)).headers
        assert h["x-content-type-options"] == "nosniff"
        assert h["x-frame-options"] == "DENY"
        assert h["referrer-policy"] == "no-referrer"
        assert "no-store" in h["cache-control"]


async def test_hsts_is_not_sent_in_development(client):
    assert "strict-transport-security" not in (await client.get("/api/v1/health")).headers
