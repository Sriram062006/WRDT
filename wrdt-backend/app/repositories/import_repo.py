"""ImportHistory repository — plain data access, no business rules (see base.py)."""
from __future__ import annotations

import uuid

from sqlalchemy import select

from app.models.import_history import ImportHistory
from app.repositories.base import BaseRepository


class ImportHistoryRepository(BaseRepository[ImportHistory]):
    model = ImportHistory

    async def list_by_organization(
        self, organization_id: uuid.UUID, *, offset: int = 0, limit: int = 20
    ) -> list[ImportHistory]:
        stmt = (
            select(ImportHistory)
            .where(ImportHistory.organization_id == organization_id)
            .order_by(ImportHistory.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())
