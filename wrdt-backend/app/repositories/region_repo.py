"""Region repository — plain data access, no business rules (see base.py)."""
from __future__ import annotations

import uuid

from sqlalchemy import func, select

from app.models.group import Group
from app.models.member import Member
from app.models.region import Region
from app.repositories.base import BaseRepository


class RegionRepository(BaseRepository[Region]):
    model = Region

    async def get_by_name_ci(self, organization_id: uuid.UUID, name: str) -> Region | None:
        stmt = select(Region).where(
            Region.organization_id == organization_id,
            func.lower(Region.name) == name.strip().lower(),
            Region.deleted_at.is_(None),
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_organization(
        self, organization_id: uuid.UUID, *, offset: int, limit: int, q: str | None = None
    ) -> list[Region]:
        stmt = self._base_query().where(Region.organization_id == organization_id)
        if q:
            stmt = stmt.where(Region.name.ilike(f"%{q}%"))
        stmt = stmt.offset(offset).limit(limit)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def count_by_organization(self, organization_id: uuid.UUID, *, q: str | None = None) -> int:
        stmt = select(func.count()).select_from(
            self._base_query().where(Region.organization_id == organization_id).subquery()
        )
        if q:
            # subquery already filtered by org; re-derive with name filter for an accurate count
            stmt = select(func.count()).select_from(
                self._base_query()
                .where(Region.organization_id == organization_id, Region.name.ilike(f"%{q}%"))
                .subquery()
            )
        result = await self.db.execute(stmt)
        return result.scalar_one()

    async def counts_for_region(self, region_id: uuid.UUID) -> tuple[int, int]:
        """Returns (groups_count, members_count) computed live — replaces the
        frontend mock's denormalized counters with a real query, since the
        DB schema doesn't persist a redundant counter column (single source
        of truth: the rows themselves)."""
        groups_count = await self.db.scalar(
            select(func.count()).select_from(Group).where(
                Group.region_id == region_id, Group.deleted_at.is_(None)
            )
        )
        members_count = await self.db.scalar(
            select(func.count())
            .select_from(Member)
            .join(Group, Member.group_id == Group.id)
            .where(Group.region_id == region_id, Member.deleted_at.is_(None))
        )
        return groups_count or 0, members_count or 0
