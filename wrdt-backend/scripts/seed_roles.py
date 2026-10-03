"""
Idempotent seed for the two v1.0 roles: owner and supervisor.

Run with:  python -m scripts.seed_roles

The original version blindly inserted both rows, so a second run failed
on the unique index and left the transaction aborted. It now upserts, so
it is safe to run on every deploy -- which is what you want, because
permission keys change over time and the seeded bag is the source of
truth for `require_permission`.
"""
from __future__ import annotations

import asyncio

from sqlalchemy import select

from app.db.session import AsyncSessionLocal, engine
from app.models.role import Role

OWNER_PERMISSIONS = {
    "region.create": True, "region.read": True, "region.update": True, "region.delete": True,
    "group.create": True, "group.read": True, "group.update": True, "group.delete": True,
    "member.create": True, "member.read": True, "member.update": True, "member.delete": True,
    "meeting.start": True, "meeting.draft": True, "meeting.complete": True, "meeting.read": True,
    "import.run": True,
    "user.manage": True,
    "settings.manage": True,
    "reports.view": True,
    "activity.view": True,
}

SUPERVISOR_PERMISSIONS = {
    "region.read": False,
    "group.read": True,           # only their assigned groups -- scoping enforced server-side
    "member.read": True,
    "meeting.start": True, "meeting.draft": True, "meeting.complete": True, "meeting.read": True,
    "reports.view": True,
    # explicitly no region/group deletion or system administration
    "region.delete": False, "group.delete": False, "user.manage": False,
    "settings.manage": False, "import.run": False, "activity.view": False,
}

ROLES = [
    ("owner", "Full system access", OWNER_PERMISSIONS),
    (
        "supervisor",
        "Runs meetings for assigned groups; no region/group deletion or admin",
        SUPERVISOR_PERMISSIONS,
    ),
]


async def seed_roles() -> None:
    async with AsyncSessionLocal() as db:
        for name, description, permissions in ROLES:
            existing = (
                await db.execute(select(Role).where(Role.name == name))
            ).scalar_one_or_none()
            if existing:
                existing.description = description
                existing.permissions = permissions
                print(f"updated role: {name}")
            else:
                db.add(Role(name=name, description=description, permissions=permissions))
                print(f"created role: {name}")
        await db.commit()


async def _main() -> None:
    await seed_roles()
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(_main())
