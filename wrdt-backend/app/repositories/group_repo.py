"""Group repository -- plain data access, no business rules (see base.py).

List queries return `(Group, members_count)` pairs computed by a single
correlated scalar subquery rather than one COUNT per row: the previous
per-group count was an N+1 that turned a 50-group page into 51 round
trips against a remote (Supabase) database.
"""
from __future__ import annotations

import uuid
from collections.abc import Iterable

from sqlalchemy import Select, func, select

from app.models.group import Group
from app.models.member import Member
from app.models.region import Region
from app.repositories.base import BaseRepository


def _members_count_subquery():
    return (
        select(func.count())
        .select_from(Member)
        .where(Member.group_id == Group.id, Member.deleted_at.is_(None))
        .correlate(Group)
        .scalar_subquery()
    )


class GroupRepository(BaseRepository[Group]):
    model = Group

    async def get_by_name_ci(self, region_id: uuid.UUID, name: str) -> Group | None:
        stmt = select(Group).where(
            Group.region_id == region_id,
            func.lower(Group.name) == name.strip().lower(),
            Group.deleted_at.is_(None),
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    # -- shared query builders ------------------------------------------
    def _filtered(
        self,
        *,
        region_id: uuid.UUID | None = None,
        organization_id: uuid.UUID | None = None,
        q: str | None = None,
        allowed_group_ids: Iterable[uuid.UUID] | None = None,
    ) -> Select:
        stmt = select(Group).where(Group.deleted_at.is_(None))
        if organization_id is not None:
            stmt = stmt.join(Region, Group.region_id == Region.id).where(
                Region.organization_id == organization_id, Region.deleted_at.is_(None)
            )
        if region_id is not None:
            stmt = stmt.where(Group.region_id == region_id)
        if q:
            stmt = stmt.where(Group.name.ilike(f"%{q}%"))
        if allowed_group_ids is not None:
            ids = list(allowed_group_ids)
            # An empty allow-list must match nothing, not everything.
            stmt = stmt.where(Group.id.in_(ids) if ids else False)
        return stmt

    async def list_with_counts(
        self,
        *,
        region_id: uuid.UUID | None = None,
        organization_id: uuid.UUID | None = None,
        offset: int = 0,
        limit: int = 20,
        q: str | None = None,
        allowed_group_ids: Iterable[uuid.UUID] | None = None,
    ) -> list[tuple[Group, int]]:
        base = self._filtered(
            region_id=region_id,
            organization_id=organization_id,
            q=q,
            allowed_group_ids=allowed_group_ids,
        )
        stmt = (
            base.add_columns(_members_count_subquery().label("members_count"))
            .order_by(Group.name.asc())
            .offset(offset)
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        return [(row[0], row[1] or 0) for row in result.all()]

    async def count_filtered(
        self,
        *,
        region_id: uuid.UUID | None = None,
        organization_id: uuid.UUID | None = None,
        q: str | None = None,
        allowed_group_ids: Iterable[uuid.UUID] | None = None,
    ) -> int:
        base = self._filtered(
            region_id=region_id,
            organization_id=organization_id,
            q=q,
            allowed_group_ids=allowed_group_ids,
        )
        stmt = select(func.count()).select_from(base.subquery())
        result = await self.db.execute(stmt)
        return result.scalar_one()

    async def members_count(self, group_id: uuid.UUID) -> int:
        result = await self.db.scalar(
            select(func.count())
            .select_from(Member)
            .where(Member.group_id == group_id, Member.deleted_at.is_(None))
        )
        return result or 0

    async def list_by_region(
        self, region_id: uuid.UUID, *, offset: int, limit: int, q: str | None = None
    ) -> list[Group]:
        stmt = self._filtered(region_id=region_id, q=q).offset(offset).limit(limit)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def list_by_ids(self, group_ids: list[uuid.UUID]) -> list[Group]:
        if not group_ids:
            return []
        stmt = self._base_query().where(Group.id.in_(group_ids))
        result = await self.db.execute(stmt)
        return list(result.scalars().all())
