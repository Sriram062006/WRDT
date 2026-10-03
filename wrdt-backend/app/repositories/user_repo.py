"""User repository — plain data access, no business rules (see base.py)."""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.models.user import User, UserGroupAssignment
from app.repositories.base import BaseRepository


class UserRepository(BaseRepository[User]):
    model = User

    async def get_by_email(self, email: str) -> User | None:
        stmt = select(User).where(
            User.email == email.lower().strip(), User.deleted_at.is_(None)
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_with_role(self, id_: uuid.UUID) -> User | None:
        stmt = (
            select(User)
            .where(User.id == id_, User.deleted_at.is_(None))
            .options(selectinload(User.role))
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_organization(
        self, organization_id: uuid.UUID, *, offset: int = 0, limit: int = 20
    ) -> list[User]:
        stmt = (
            select(User)
            .where(User.organization_id == organization_id, User.deleted_at.is_(None))
            .offset(offset)
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_assigned_group_ids(self, user_id: uuid.UUID) -> list[uuid.UUID]:
        stmt = select(UserGroupAssignment.group_id).where(UserGroupAssignment.user_id == user_id)
        result = await self.db.execute(stmt)
        return [row[0] for row in result.all()]

    async def get_assignment(self, user_id: uuid.UUID, group_id: uuid.UUID) -> UserGroupAssignment | None:
        stmt = select(UserGroupAssignment).where(
            UserGroupAssignment.user_id == user_id, UserGroupAssignment.group_id == group_id
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    def add_assignment(self, user_id: uuid.UUID, group_id: uuid.UUID) -> UserGroupAssignment:
        assignment = UserGroupAssignment(user_id=user_id, group_id=group_id)
        self.db.add(assignment)
        return assignment

    async def remove_assignment(self, assignment: UserGroupAssignment) -> None:
        await self.db.delete(assignment)
