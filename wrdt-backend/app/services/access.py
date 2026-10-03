"""
Tenant-isolation / object-level access control.

Every route that receives an entity ID from the client must resolve that
ID *through this module* rather than fetching it directly, because a bare
`SELECT ... WHERE id = :id` says nothing about which organization the row
belongs to. Without these checks an authenticated Owner of organization A
could read or mutate organization B's regions, groups, members and
meetings simply by guessing/holding a UUID (IDOR across tenants).

Two layers are applied, in this order:

  1. Tenant scope  — the row must resolve, via its parent chain, to the
     caller's `organization_id`. A row in another organization is reported
     as 404 (not 403) so the API does not confirm the existence of
     identifiers belonging to other tenants.
  2. Role scope    — Supervisors are additionally restricted to the groups
     in their `user_group_assignments`. Owners are unrestricted *within
     their own organization only*.

All helpers return the resolved ORM object so callers do not need a second
round trip.
"""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, PermissionDeniedError
from app.models.group import Group
from app.models.meeting import Meeting
from app.models.member import Member
from app.models.region import Region
from app.schemas.auth import CurrentUser


async def resolve_region(db: AsyncSession, user: CurrentUser, region_id: uuid.UUID) -> Region:
    stmt = select(Region).where(
        Region.id == region_id,
        Region.organization_id == user.organization_id,
        Region.deleted_at.is_(None),
    )
    region = (await db.execute(stmt)).scalar_one_or_none()
    if region is None:
        raise NotFoundError("Region not found.")
    return region


async def resolve_group(db: AsyncSession, user: CurrentUser, group_id: uuid.UUID) -> Group:
    """Tenant check only — does NOT apply supervisor group scoping.
    Use `assert_group_access` for anything a Supervisor can reach."""
    stmt = (
        select(Group)
        .join(Region, Group.region_id == Region.id)
        .where(
            Group.id == group_id,
            Region.organization_id == user.organization_id,
            Group.deleted_at.is_(None),
            Region.deleted_at.is_(None),
        )
    )
    group = (await db.execute(stmt)).scalar_one_or_none()
    if group is None:
        raise NotFoundError("Group not found.")
    return group


async def assert_group_access(db: AsyncSession, user: CurrentUser, group_id: uuid.UUID) -> Group:
    """
    Tenant check + role check. Owners may reach any group inside their own
    organization; Supervisors only the groups explicitly assigned to them.

    A Supervisor hitting a group that exists in their org but isn't theirs
    gets 403 (the group demonstrably exists to their Owner, so hiding it
    buys nothing and a clear error is more useful); a group in *another*
    organization is still 404 via `resolve_group`.
    """
    group = await resolve_group(db, user, group_id)
    if user.role_name != "owner" and group.id not in user.assigned_group_ids:
        raise PermissionDeniedError("You do not have access to this group.")
    return group


async def resolve_member(db: AsyncSession, user: CurrentUser, member_id: uuid.UUID) -> Member:
    stmt = (
        select(Member)
        .join(Group, Member.group_id == Group.id)
        .join(Region, Group.region_id == Region.id)
        .where(
            Member.id == member_id,
            Region.organization_id == user.organization_id,
            Member.deleted_at.is_(None),
            Group.deleted_at.is_(None),
        )
    )
    member = (await db.execute(stmt)).scalar_one_or_none()
    if member is None:
        raise NotFoundError("Member not found.")
    if user.role_name != "owner" and member.group_id not in user.assigned_group_ids:
        raise PermissionDeniedError("You do not have access to this member's group.")
    return member


async def resolve_meeting(db: AsyncSession, user: CurrentUser, meeting_id: uuid.UUID) -> Meeting:
    """
    Resolves a meeting by ID *and* proves the caller may touch it. This is
    what makes the meeting routes IDOR-safe even though their URLs contain
    only a meeting_id and no group_id.
    """
    stmt = (
        select(Meeting)
        .join(Group, Meeting.group_id == Group.id)
        .join(Region, Group.region_id == Region.id)
        .where(
            Meeting.id == meeting_id,
            Region.organization_id == user.organization_id,
            Group.deleted_at.is_(None),
        )
    )
    meeting = (await db.execute(stmt)).scalar_one_or_none()
    if meeting is None:
        raise NotFoundError("Meeting not found.")
    if user.role_name != "owner" and meeting.group_id not in user.assigned_group_ids:
        raise PermissionDeniedError("You do not have access to this group's meetings.")
    return meeting


async def visible_group_ids(db: AsyncSession, user: CurrentUser) -> list[uuid.UUID]:
    """Every group the caller may see: all groups in their organization for
    an Owner, or exactly their assignments for a Supervisor."""
    if user.role_name != "owner":
        return list(user.assigned_group_ids)
    stmt = (
        select(Group.id)
        .join(Region, Group.region_id == Region.id)
        .where(
            Region.organization_id == user.organization_id,
            Group.deleted_at.is_(None),
            Region.deleted_at.is_(None),
        )
    )
    return [row[0] for row in (await db.execute(stmt)).all()]
