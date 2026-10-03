"""Member repository — plain data access, no business rules (see base.py)."""
from __future__ import annotations

import uuid

from collections.abc import Iterable

from sqlalchemy import Select, func, or_, select

from app.models.group import Group
from app.models.member import Member
from app.models.region import Region
from app.repositories.base import BaseRepository


class MemberRepository(BaseRepository[Member]):
    model = Member

    async def get_by_name_ci(self, group_id: uuid.UUID, name: str) -> Member | None:
        stmt = select(Member).where(
            Member.group_id == group_id,
            func.lower(Member.name) == name.strip().lower(),
            Member.deleted_at.is_(None),
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_group(
        self, group_id: uuid.UUID, *, offset: int, limit: int, q: str | None = None
    ) -> list[Member]:
        stmt = self._base_query().where(Member.group_id == group_id)
        if q:
            stmt = stmt.where(or_(Member.name.ilike(f"%{q}%"), Member.code.ilike(f"%{q}%")))
        stmt = stmt.order_by(Member.code.asc()).offset(offset).limit(limit)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def count_by_group(self, group_id: uuid.UUID, *, q: str | None = None) -> int:
        stmt = self._base_query().where(Member.group_id == group_id)
        if q:
            stmt = stmt.where(or_(Member.name.ilike(f"%{q}%"), Member.code.ilike(f"%{q}%")))
        count_stmt = select(func.count()).select_from(stmt.subquery())
        result = await self.db.execute(count_stmt)
        return result.scalar_one()

    async def count_existing_in_group(self, group_id: uuid.UUID) -> int:
        """Next sequential member code (LM001, LM002...). Counts
        soft-deleted members too, on purpose: reusing a departed member's
        code would make two different people share an identifier in the
        historical ledger."""
        result = await self.db.scalar(
            select(func.count()).select_from(Member).where(Member.group_id == group_id)
        )
        return result or 0

    # -- org-wide (flat) listing ---------------------------------------
    def _org_filtered(
        self,
        organization_id: uuid.UUID,
        *,
        group_id: uuid.UUID | None = None,
        region_id: uuid.UUID | None = None,
        q: str | None = None,
        allowed_group_ids: Iterable[uuid.UUID] | None = None,
    ) -> Select:
        stmt = (
            select(Member, Group, Region)
            .join(Group, Member.group_id == Group.id)
            .join(Region, Group.region_id == Region.id)
            .where(
                Region.organization_id == organization_id,
                Member.deleted_at.is_(None),
                Group.deleted_at.is_(None),
                Region.deleted_at.is_(None),
            )
        )
        if group_id is not None:
            stmt = stmt.where(Member.group_id == group_id)
        if region_id is not None:
            stmt = stmt.where(Group.region_id == region_id)
        if q:
            # Members are looked up by code as often as by name on the
            # floor, so search both.
            stmt = stmt.where(
                or_(Member.name.ilike(f"%{q}%"), Member.code.ilike(f"%{q}%"))
            )
        if allowed_group_ids is not None:
            ids = list(allowed_group_ids)
            stmt = stmt.where(Member.group_id.in_(ids) if ids else False)
        return stmt

    async def list_for_org(
        self,
        organization_id: uuid.UUID,
        *,
        offset: int = 0,
        limit: int = 20,
        group_id: uuid.UUID | None = None,
        region_id: uuid.UUID | None = None,
        q: str | None = None,
        allowed_group_ids: Iterable[uuid.UUID] | None = None,
    ) -> list[tuple[Member, Group, Region]]:
        stmt = (
            self._org_filtered(
                organization_id, group_id=group_id, region_id=region_id,
                q=q, allowed_group_ids=allowed_group_ids,
            )
            .order_by(Member.code.asc())
            .offset(offset)
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        return [(r[0], r[1], r[2]) for r in result.all()]

    async def count_for_org(
        self,
        organization_id: uuid.UUID,
        *,
        group_id: uuid.UUID | None = None,
        region_id: uuid.UUID | None = None,
        q: str | None = None,
        allowed_group_ids: Iterable[uuid.UUID] | None = None,
    ) -> int:
        base = self._org_filtered(
            organization_id, group_id=group_id, region_id=region_id,
            q=q, allowed_group_ids=allowed_group_ids,
        )
        stmt = select(func.count()).select_from(base.subquery())
        return (await self.db.execute(stmt)).scalar_one()
