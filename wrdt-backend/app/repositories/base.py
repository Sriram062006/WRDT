"""
Generic repository base class.

Repositories are the ONLY layer allowed to build SQLAlchemy queries. They
know nothing about business rules (no "is this meeting locked?" checks
here) — that belongs in services/. This split is what lets the ledger
engine (Phase 7) be unit-tested with a fake/mock repository, independent of
a real database.

Soft-delete aware by default: `get`, `list`, and `delete` all respect
`deleted_at IS NULL` for any model that uses SoftDeleteMixin.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Generic, TypeVar

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import Base, SoftDeleteMixin

ModelT = TypeVar("ModelT", bound=Base)


class BaseRepository(Generic[ModelT]):
    model: type[ModelT]

    def __init__(self, db: AsyncSession):
        self.db = db

    def _base_query(self):
        stmt = select(self.model)
        if issubclass(self.model, SoftDeleteMixin):
            stmt = stmt.where(self.model.deleted_at.is_(None))
        return stmt

    async def get(self, id_: uuid.UUID) -> ModelT | None:
        stmt = self._base_query().where(self.model.id == id_)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def list(self, *, offset: int = 0, limit: int = 20) -> list[ModelT]:
        stmt = self._base_query().offset(offset).limit(limit)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def count(self) -> int:
        stmt = select(func.count()).select_from(self._base_query().subquery())
        result = await self.db.execute(stmt)
        return result.scalar_one()

    def add(self, instance: ModelT) -> ModelT:
        self.db.add(instance)
        return instance

    async def delete(self, instance: ModelT) -> None:
        """Soft delete if supported, otherwise a real DELETE."""
        if isinstance(instance, SoftDeleteMixin):
            instance.deleted_at = datetime.now(timezone.utc)
        else:
            await self.db.delete(instance)

    async def flush(self) -> None:
        await self.db.flush()

    async def commit(self) -> None:
        await self.db.commit()

    async def commit_refresh(self, instance: ModelT) -> ModelT:
        """Commit, then reload the instance.

        `updated_at` carries a server-side `onupdate=now()`, so after an
        UPDATE SQLAlchemy marks it stale and re-reads it on next access.
        Under asyncio that lazy read happens outside the greenlet and
        raises MissingGreenlet -- which surfaced as a 500 on every route
        that returned a just-modified row (saving a single ledger entry,
        overriding a loan, editing an expense). Refreshing explicitly
        inside the async context is the supported way to get the
        server-generated values back.
        """
        await self.db.commit()
        await self.db.refresh(instance)
        return instance
