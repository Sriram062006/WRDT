"""
Region service — CRUD + business rules, 1:1 with the frontend's
createRegion / updateRegion / deleteRegion functions:

  - name required, trimmed
  - name uniqueness case-insensitive, scoped to organization
  - delete cascades to Groups -> Members -> Meetings (soft delete, see
    module docstring on SoftDeleteMixin: hard-delete would break
    referential integrity for locked meeting history)
"""
from __future__ import annotations

import uuid

from app.core.exceptions import DuplicateError, NotFoundError, ValidationAppError
from app.models.region import Region
from app.repositories.region_repo import RegionRepository
from app.schemas.region import RegionCreate, RegionUpdate, RegionWithCounts
from app.services.audit_service import AuditService
from app.services.base import BaseService
from app.services.group_service import GroupService


class RegionService(BaseService):
    def __init__(self, db):
        super().__init__(db)
        self.regions = RegionRepository(db)
        self.audit = AuditService(db)

    async def get_or_404(self, region_id: uuid.UUID) -> Region:
        region = await self.regions.get(region_id)
        if not region:
            raise NotFoundError("Region not found.")
        return region

    async def get_with_counts(self, region_id: uuid.UUID) -> RegionWithCounts:
        region = await self.get_or_404(region_id)
        groups_count, members_count = await self.regions.counts_for_region(region.id)
        return RegionWithCounts(
            id=region.id,
            created_at=region.created_at,
            updated_at=region.updated_at,
            organization_id=region.organization_id,
            name=region.name,
            status=region.status,
            groups_count=groups_count,
            members_count=members_count,
        )

    async def list_regions(
        self, organization_id: uuid.UUID, *, offset: int, limit: int, q: str | None = None
    ) -> tuple[list[RegionWithCounts], int]:
        regions = await self.regions.list_by_organization(organization_id, offset=offset, limit=limit, q=q)
        total = await self.regions.count_by_organization(organization_id, q=q)
        items = []
        for region in regions:
            groups_count, members_count = await self.regions.counts_for_region(region.id)
            items.append(
                RegionWithCounts(
                    id=region.id,
                    created_at=region.created_at,
                    updated_at=region.updated_at,
                    organization_id=region.organization_id,
                    name=region.name,
                    status=region.status,
                    groups_count=groups_count,
                    members_count=members_count,
                )
            )
        return items, total

    async def create_region(
        self, organization_id: uuid.UUID, payload: RegionCreate, actor_id: uuid.UUID | None
    ) -> Region:
        name = payload.name.strip()
        if not name:
            raise ValidationAppError("Region name is required.")
        if await self.regions.get_by_name_ci(organization_id, name):
            raise DuplicateError("A region with this name already exists.")

        region = Region(organization_id=organization_id, name=name, status="Active", created_by=actor_id)
        self.regions.add(region)
        await self.regions.flush()
        await self.audit.record(
            actor_id=actor_id, action="region.create", entity_type="region",
            entity_id=region.id, after={"name": name},
        )
        return await self.regions.commit_refresh(region)

    async def update_region(
        self, region_id: uuid.UUID, payload: RegionUpdate, actor_id: uuid.UUID | None
    ) -> Region:
        region = await self.get_or_404(region_id)
        before = {"name": region.name, "status": region.status}

        if payload.name is not None:
            name = payload.name.strip()
            if not name:
                raise ValidationAppError("Region name is required.")
            existing = await self.regions.get_by_name_ci(region.organization_id, name)
            if existing and existing.id != region.id:
                raise DuplicateError("Another region already has this name.")
            region.name = name

        if payload.status is not None:
            region.status = payload.status

        await self.regions.flush()
        await self.audit.record(
            actor_id=actor_id, action="region.update", entity_type="region",
            entity_id=region.id, before=before, after={"name": region.name, "status": region.status},
        )
        return await self.regions.commit_refresh(region)

    async def delete_region(self, region_id: uuid.UUID, actor_id: uuid.UUID | None) -> None:
        region = await self.get_or_404(region_id)

        # Cascade: soft-delete every Group in this region (which itself
        # cascades to Members) — mirrors the frontend's deleteRegion() ->
        # deleteGroup() -> deleteMember() cascade, but as soft deletes.
        group_service = GroupService(self.db)
        groups, _ = await group_service.list_groups(region_id, offset=0, limit=10_000)
        for group in groups:
            await group_service.delete_group(group.id, actor_id)

        await self.regions.delete(region)
        await self.audit.record(
            actor_id=actor_id, action="region.delete", entity_type="region",
            entity_id=region.id, before={"name": region.name},
        )
        await self.regions.commit()
