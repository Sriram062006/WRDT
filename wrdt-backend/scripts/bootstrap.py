"""
First-run bootstrap: create an Organization and its first Owner account.

Without this there is no way into a freshly migrated database -- every
route requires authentication and nothing can create the first user,
which made the shipped backend unusable on a clean deploy.

Usage (interactive):
    python -m scripts.bootstrap

Usage (non-interactive, for CI or a provisioning script):
    python -m scripts.bootstrap \
        --org "WRDT Krishnagiri" \
        --email owner@example.org \
        --name "Field Director" \
        --password-env WRDT_BOOTSTRAP_PASSWORD

The password is never accepted as a command-line argument: argv is
visible to every process on the host and lands in shell history.
"""
from __future__ import annotations

import argparse
import asyncio
import getpass
import os
import sys

from sqlalchemy import func, select

from app.core.security import hash_password
from app.db.session import AsyncSessionLocal, engine
from app.models.organization import Organization
from app.models.role import Role
from app.models.user import User
from scripts.seed_roles import seed_roles

MIN_PASSWORD_LENGTH = 10


def _parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Create the first organization and Owner user.")
    p.add_argument("--org", help="Organization name")
    p.add_argument("--email", help="Owner email address")
    p.add_argument("--name", help="Owner full name")
    p.add_argument(
        "--password-env",
        default="WRDT_BOOTSTRAP_PASSWORD",
        help="Environment variable holding the Owner password (default: WRDT_BOOTSTRAP_PASSWORD)",
    )
    return p.parse_args(argv)


def _prompt(label: str, provided: str | None) -> str:
    if provided:
        return provided
    value = input(f"{label}: ").strip()
    if not value:
        print(f"{label} is required.", file=sys.stderr)
        raise SystemExit(1)
    return value


def _resolve_password(env_var: str) -> str:
    password = os.environ.get(env_var)
    if not password:
        password = getpass.getpass("Owner password: ")
        confirm = getpass.getpass("Confirm password: ")
        if password != confirm:
            print("Passwords do not match.", file=sys.stderr)
            raise SystemExit(1)
    if len(password) < MIN_PASSWORD_LENGTH:
        print(
            f"Password must be at least {MIN_PASSWORD_LENGTH} characters.",
            file=sys.stderr,
        )
        raise SystemExit(1)
    return password


async def bootstrap(org_name: str, email: str, full_name: str, password: str) -> None:
    await seed_roles()

    async with AsyncSessionLocal() as db:
        owner_role = (
            await db.execute(select(Role).where(Role.name == "owner"))
        ).scalar_one_or_none()
        if owner_role is None:
            raise SystemExit("Owner role missing; run `python -m scripts.seed_roles` first.")

        email = email.lower().strip()
        existing_user = (
            await db.execute(select(User).where(func.lower(User.email) == email))
        ).scalar_one_or_none()
        if existing_user:
            raise SystemExit(f"A user with email {email} already exists. Nothing was changed.")

        org = (
            await db.execute(select(Organization).where(Organization.name == org_name))
        ).scalar_one_or_none()
        if org is None:
            org = Organization(name=org_name, status="Active")
            db.add(org)
            await db.flush()
            print(f"created organization: {org_name}")
        else:
            print(f"using existing organization: {org_name}")

        db.add(
            User(
                organization_id=org.id,
                role_id=owner_role.id,
                email=email,
                password_hash=hash_password(password),
                full_name=full_name,
                is_active=True,
            )
        )
        await db.commit()
        print(f"created Owner: {email}")
        print("\nBootstrap complete. Sign in at the frontend with this account.")


async def _main(argv: list[str]) -> None:
    args = _parse_args(argv)
    org_name = _prompt("Organization name", args.org)
    email = _prompt("Owner email", args.email)
    full_name = _prompt("Owner full name", args.name)
    password = _resolve_password(args.password_env)
    try:
        await bootstrap(org_name, email, full_name, password)
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(_main(sys.argv[1:]))
