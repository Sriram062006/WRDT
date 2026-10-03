"""
Group service — CRUD + business rules, 1:1 with the frontend's
createGroup / updateGroup / deleteGroup functions:

  - name required, trimmed
  - name uniqueness case-insensitive, scoped to region
  - formed_date defaults to today if not supplied
  - delete cascades to Members (soft delete)
"""
from __future__ import annotations

import uuid
from datetime import date

from app.core.exceptions import DuplicateError, NotFoundError, ValidationAppError
from app.models.group import Group
from app.repositories.group_repo import GroupRepository
from app.repositories.region_repo import RegionRepository
from app.schemas.group import GroupCreate, GroupUpdate, GroupWithCounts
from app.services.audit_service import AuditService
from app.services.base import BaseService


class GroupService(BaseService):
    def __init__(self, db):
        super().__init__(db)
        self.groups = GroupRepository(db)
        self.regions = RegionRepository(db)
        self.audit = AuditService(db)

    async def get_or_404(self, group_id: uuid.UUID) -> Group:
        group = await self.groups.get(group_id)
        if not group:
            raise NotFoundError("Group not found.")
        return group

    async def get_with_counts(self, group_id: uuid.UUID) -> GroupWithCounts:
        group = await self.get_or_404(group_id)
        members_count = await self.groups.members_count(group.id)
        return GroupWithCounts(
            id=group.id,
            created_at=group.created_at,
            updated_at=group.updated_at,
            region_id=group.region_id,
            name=group.name,
            formed_date=group.formed_date,
            status=group.status,
            members_count=members_count,
        )

    async def list_groups(
        self,
        region_id: uuid.UUID,
        *,
        offset: int,
        limit: int,
        q: str | None = None,
        allowed_group_ids: set[uuid.UUID] | None = None,
    ) -> tuple[list[GroupWithCounts], int]:
        """Groups inside one region. `allowed_group_ids` is the Supervisor
        scope; filtering it in SQL (rather than trimming the page in
        Python, as an earlier version did) keeps `total` honest and stops
        a Supervisor's page from silently shrinking."""
        rows = await self.groups.list_with_counts(
            region_id=region_id, offset=offset, limit=limit, q=q,
            allowed_group_ids=allowed_group_ids,
        )
        total = await self.groups.count_filtered(
            region_id=region_id, q=q, allowed_group_ids=allowed_group_ids
        )
        return [_to_counts(g, c) for g, c in rows], total

    async def list_groups_for_org(
        self,
        organization_id: uuid.UUID,
        *,
        offset: int,
        limit: int,
        q: str | None = None,
        region_id: uuid.UUID | None = None,
        allowed_group_ids: set[uuid.UUID] | None = None,
    ) -> tuple[list[GroupWithCounts], int]:
        rows = await self.groups.list_with_counts(
            organization_id=organization_id, region_id=region_id,
            offset=offset, limit=limit, q=q, allowed_group_ids=allowed_group_ids,
        )
        total = await self.groups.count_filtered(
            organization_id=organization_id, region_id=region_id, q=q,
            allowed_group_ids=allowed_group_ids,
        )
        return [_to_counts(g, c) for g, c in rows], total

    async def create_group(
        self, region_id: uuid.UUID, payload: GroupCreate, actor_id: uuid.UUID | None
    ) -> Group:
        region = await self.regions.get(region_id)
        if not region:
            raise NotFoundError("Region not found.")

        name = payload.name.strip()
        if not name:
            raise ValidationAppError("Group name is required.")
        if await self.groups.get_by_name_ci(region_id, name):
            raise DuplicateError("A group with this name already exists in this region.")

        group = Group(
            region_id=region_id,
            name=name,
            formed_date=payload.formed_date or date.today(),
            status="Active",
            created_by=actor_id,
        )
        self.groups.add(group)
        await self.groups.flush()
        await self.audit.record(
            actor_id=actor_id, action="group.create", entity_type="group",
            entity_id=group.id, after={"name": name, "region_id": str(region_id)},
        )
        return await self.groups.commit_refresh(group)

    async def update_group(
        self, group_id: uuid.UUID, payload: GroupUpdate, actor_id: uuid.UUID | None
    ) -> Group:
        group = await self.get_or_404(group_id)
        before = {"name": group.name, "status": group.status}

        if payload.name is not None:
            name = payload.name.strip()
            if not name:
                raise ValidationAppError("Group name is required.")
            existing = await self.groups.get_by_name_ci(group.region_id, name)
            if existing and existing.id != group.id:
                raise DuplicateError("Another group in this region already has this name.")
            group.name = name

        if payload.status is not None:
            group.status = payload.status

        await self.groups.flush()
        await self.audit.record(
            actor_id=actor_id, action="group.update", entity_type="group",
            entity_id=group.id, before=before, after={"name": group.name, "status": group.status},
        )
        return await self.groups.commit_refresh(group)

    async def delete_group(self, group_id: uuid.UUID, actor_id: uuid.UUID | None) -> None:
        # Local import to avoid a circular import (member_service does not
        # import group_service, so this direction is safe).
        from app.services.member_service import MemberService

        group = await self.get_or_404(group_id)

        member_service = MemberService(self.db)
        members, _ = await member_service.list_members(group_id, offset=0, limit=10_000)
        for member in members:
            await member_service.delete_member(member.id, actor_id)

        await self.groups.delete(group)
        await self.audit.record(
            actor_id=actor_id, action="group.delete", entity_type="group",
            entity_id=group.id, before={"name": group.name},
        )
        await self.groups.commit()


def _to_counts(group: Group, members_count: int) -> GroupWithCounts:
    return GroupWithCounts(
        id=group.id,
        created_at=group.created_at,
        updated_at=group.updated_at,
        region_id=group.region_id,
        name=group.name,
        formed_date=group.formed_date,
        status=group.status,
        members_count=members_count,
    )
