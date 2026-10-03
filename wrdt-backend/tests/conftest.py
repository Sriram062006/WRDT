"""
Test harness.

The project shipped with empty `tests/` packages and no fixtures, so
nothing about the money logic or the access rules was actually verified.
These fixtures give every test a real PostgreSQL schema (the ledger logic
leans on Postgres triggers, partial unique indexes and NUMERIC
arithmetic, so SQLite would not be testing the same system) and an
in-process HTTP client that exercises the genuine FastAPI stack:
middleware, dependency injection, auth, serialisation and all.
"""
from __future__ import annotations

import asyncio
import os
import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

TEST_DB_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+asyncpg://postgres:postgres@127.0.0.1:5432/wrdt_test"
)
TEST_DB_URL_SYNC = TEST_DB_URL.replace("postgresql+asyncpg", "postgresql+psycopg2")

os.environ.setdefault("DATABASE_URL", TEST_DB_URL)
os.environ.setdefault("DATABASE_URL_SYNC", TEST_DB_URL_SYNC)
os.environ.setdefault("SECRET_KEY", "test-secret-key-not-for-production-01")
os.environ.setdefault("JWT_SECRET_KEY", "test-jwt-secret-key-not-for-production-02")
os.environ.setdefault("APP_ENV", "development")
os.environ.setdefault("DB_DISABLE_STATEMENT_CACHE", "true")


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session", autouse=True)
def _schema():
    """Build the schema once per session by running the real Alembic
    migrations -- not `metadata.create_all`. The triggers and partial
    indexes that enforce the permanent meeting lock only exist in the
    migrations, and those are precisely what the lock tests need to
    exercise."""
    from alembic import command
    from alembic.config import Config

    cfg = Config("alembic.ini")
    cfg.set_main_option("script_location", "app/db/migrations")
    cfg.set_main_option("sqlalchemy.url", TEST_DB_URL_SYNC)
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")
    yield


@pytest_asyncio.fixture
async def db():
    from app.db.session import AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        yield session


@pytest_asyncio.fixture(autouse=True)
async def _clean_tables():
    """Truncate between tests so each one starts from a known state.
    `meetings` is truncated with CASCADE because locked meetings cannot
    be deleted row-by-row -- the trigger under test would (correctly)
    refuse."""
    from app.db.session import AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        await session.execute(
            text(
                "TRUNCATE meeting_entries, expenses, meetings, members, groups, regions, "
                "import_history, audit_logs, user_group_assignments, revoked_tokens, "
                "users, organizations RESTART IDENTITY CASCADE"
            )
        )
        await session.commit()
    yield


@pytest_asyncio.fixture
async def client():
    from app.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture
async def roles():
    from scripts.seed_roles import seed_roles

    await seed_roles()


async def _make_org_and_owner(email: str, org_name: str, password: str = "OwnerPass123!"):
    from sqlalchemy import select

    from app.core.security import hash_password
    from app.db.session import AsyncSessionLocal
    from app.models.organization import Organization
    from app.models.role import Role
    from app.models.user import User

    async with AsyncSessionLocal() as db:
        owner_role = (await db.execute(select(Role).where(Role.name == "owner"))).scalar_one()
        org = Organization(name=org_name, status="Active")
        db.add(org)
        await db.flush()
        user = User(
            organization_id=org.id,
            role_id=owner_role.id,
            email=email,
            password_hash=hash_password(password),
            full_name="Owner " + org_name,
            is_active=True,
        )
        db.add(user)
        await db.commit()
        return org.id, user.id


async def _make_supervisor(org_id, email: str, password: str = "SuperPass123!"):
    from sqlalchemy import select

    from app.core.security import hash_password
    from app.db.session import AsyncSessionLocal
    from app.models.role import Role
    from app.models.user import User

    async with AsyncSessionLocal() as db:
        role = (await db.execute(select(Role).where(Role.name == "supervisor"))).scalar_one()
        user = User(
            organization_id=org_id,
            role_id=role.id,
            email=email,
            password_hash=hash_password(password),
            full_name="Supervisor",
            is_active=True,
        )
        db.add(user)
        await db.commit()
        return user.id


async def _login(client: AsyncClient, email: str, password: str) -> str:
    resp = await client.post(
        "/api/v1/auth/login", json={"email": email, "password": password}
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def owner_ctx(client, roles):
    """An organization with an Owner, already signed in."""
    suffix = uuid.uuid4().hex[:8]
    org_id, user_id = await _make_org_and_owner(f"owner-{suffix}@wrdt.example.org", f"Org {suffix}")
    token = await _login(client, f"owner-{suffix}@wrdt.example.org", "OwnerPass123!")
    return {"org_id": org_id, "user_id": user_id, "token": token, "headers": auth(token)}


@pytest_asyncio.fixture
async def other_org_ctx(client, roles):
    """A SECOND organization with its own Owner -- the counterparty for
    every tenant-isolation test."""
    suffix = uuid.uuid4().hex[:8]
    org_id, user_id = await _make_org_and_owner(f"other-{suffix}@wrdt.example.org", f"Other {suffix}")
    token = await _login(client, f"other-{suffix}@wrdt.example.org", "OwnerPass123!")
    return {"org_id": org_id, "user_id": user_id, "token": token, "headers": auth(token)}
