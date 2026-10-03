"""
User management service (Owner-only): create/update users, assign roles,
assign/unassign supervisors to groups.

Every lookup here takes the caller's `organization_id` and filters on it.
Role gating happens at the route layer; *tenant* gating happens here,
because it is a data-integrity rule that must hold no matter which route
(or future background job) calls in.
"""
from __future__ import annotations

import uuid

from sqlalchemy import func, select

from app.core.exceptions import (
    DuplicateError,
    NotFoundError,
    PermissionDeniedError,
    ValidationAppError,
)
from app.core.security import hash_password, verify_password
from app.models.group import Group
from app.models.region import Region
from app.models.role import Role
from app.models.user import User
from app.repositories.group_repo import GroupRepository
from app.repositories.region_repo import RegionRepository
from app.repositories.role_repo import RoleRepository
from app.repositories.user_repo import UserRepository
from app.schemas.auth import CurrentUser
from app.schemas.user import UserCreate, UserGroupAssignmentCreate, UserUpdate
from app.services.audit_service import AuditService
from app.services.base import BaseService


class UserService(BaseService):
    def __init__(self, db):
        super().__init__(db)
        self.users = UserRepository(db)
        self.roles = RoleRepository(db)
        self.groups = GroupRepository(db)
        self.regions = RegionRepository(db)
        self.audit = AuditService(db)

    # -- reads -----------------------------------------------------------
    async def get_user_or_404(
        self, user_id: uuid.UUID, organization_id: uuid.UUID | None = None
    ) -> User:
        user = await self.users.get(user_id)
        if not user:
            raise NotFoundError("User not found.")
        if organization_id is not None and user.organization_id != organization_id:
            # Reported as 404, not 403: confirming that an ID exists in
            # another tenant is itself a small information leak.
            raise NotFoundError("User not found.")
        return user

    async def list_users(self, organization_id: uuid.UUID, *, offset: int, limit: int) -> list[User]:
        return await self.users.list_by_organization(organization_id, offset=offset, limit=limit)

    async def count_users(self, organization_id: uuid.UUID) -> int:
        stmt = select(func.count()).select_from(User).where(
            User.organization_id == organization_id, User.deleted_at.is_(None)
        )
        return (await self.db.execute(stmt)).scalar_one()

    async def list_roles(self) -> list[Role]:
        return list((await self.db.execute(select(Role).order_by(Role.name))).scalars().all())

    async def list_assignments(self, user_id: uuid.UUID) -> list[uuid.UUID]:
        return await self.users.get_assigned_group_ids(user_id)

    # -- writes ----------------------------------------------------------
    async def create_user(self, organization_id: uuid.UUID, payload: UserCreate) -> User:
        existing = await self.users.get_by_email(payload.email)
        if existing:
            raise DuplicateError("A user with this email already exists.")

        role = await self.roles.get(payload.role_id)
        if not role:
            raise ValidationAppError("Invalid role_id.")

        user = User(
            # organization_id is taken from the authenticated caller, never
            # from the request body: accepting it from the client let an
            # Owner create accounts inside someone else's organization.
            organization_id=organization_id,
            role_id=payload.role_id,
            email=payload.email.lower().strip(),
            password_hash=hash_password(payload.password),
            full_name=payload.full_name.strip(),
            phone=payload.phone,
        )
        self.users.add(user)
        await self.users.flush()
        await self.audit.record(
            actor_id=None, action="user.create", entity_type="user", entity_id=user.id,
            after={"email": user.email, "role": role.name},
        )
        return await self.users.commit_refresh(user)

    async def update_user(
        self, user_id: uuid.UUID, payload: UserUpdate, actor: CurrentUser
    ) -> User:
        user = await self.get_user_or_404(user_id, actor.organization_id)
        before = {"full_name": user.full_name, "is_active": user.is_active, "role_id": str(user.role_id)}

        if payload.role_id is not None and payload.role_id != user.role_id:
            role = await self.roles.get(payload.role_id)
            if not role:
                raise ValidationAppError("Invalid role_id.")
            if user.id == actor.id:
                # Self-demotion locks the organization out of its own admin
                # functions if this is the last owner.
                raise ValidationAppError("You cannot change your own role.")
            await self._assert_not_last_owner(user, changing_role_to=role.name)
            user.role_id = payload.role_id

        if payload.full_name is not None:
            user.full_name = payload.full_name.strip()
        if payload.phone is not None:
            user.phone = payload.phone
        if payload.is_active is not None:
            if user.id == actor.id and payload.is_active is False:
                raise ValidationAppError("You cannot deactivate your own account.")
            if payload.is_active is False:
                await self._assert_not_last_owner(user)
            user.is_active = payload.is_active

        await self.users.flush()
        await self.audit.record(
            actor_id=actor.id, action="user.update", entity_type="user", entity_id=user.id,
            before=before,
            after={"full_name": user.full_name, "is_active": user.is_active, "role_id": str(user.role_id)},
        )
        return await self.users.commit_refresh(user)

    async def change_password(
        self, user_id: uuid.UUID, current_password: str, new_password: str
    ) -> None:
        user = await self.get_user_or_404(user_id)
        if not verify_password(current_password, user.password_hash):
            raise PermissionDeniedError("Current password is incorrect.")
        user.password_hash = hash_password(new_password)
        await self.users.flush()
        await self.audit.record(
            actor_id=user.id, action="user.change_password", entity_type="user", entity_id=user.id,
        )
        await self.users.commit()

    async def reset_password(
        self, user_id: uuid.UUID, new_password: str, actor: CurrentUser
    ) -> None:
        """Owner-driven reset. There is no self-service email reset flow in
        v1.0 -- these are shared rural field accounts without reliable
        inboxes, so the Owner re-issues the password out of band."""
        user = await self.get_user_or_404(user_id, actor.organization_id)
        user.password_hash = hash_password(new_password)
        await self.users.flush()
        await self.audit.record(
            actor_id=actor.id, action="user.reset_password", entity_type="user", entity_id=user.id,
        )
        await self.users.commit()

    async def deactivate_user(self, user_id: uuid.UUID, actor: CurrentUser) -> None:
        """Users are deactivated, not hard-deleted, for the same audit-trail
        reasons as Region/Group/Member soft delete."""
        user = await self.get_user_or_404(user_id, actor.organization_id)
        if user.id == actor.id:
            raise ValidationAppError("You cannot deactivate your own account.")
        await self._assert_not_last_owner(user)
        user.is_active = False
        await self.users.delete(user)  # sets deleted_at via SoftDeleteMixin
        await self.audit.record(
            actor_id=actor.id, action="user.deactivate", entity_type="user", entity_id=user.id,
            before={"email": user.email},
        )
        await self.users.commit()

    async def _assert_not_last_owner(self, user: User, *, changing_role_to: str | None = None) -> None:
        """Refuse any change that would leave an organization with zero
        active Owners -- that state is unrecoverable through the UI."""
        owner_role = await self.roles.get_by_name("owner")
        if not owner_role or user.role_id != owner_role.id:
            return
        if changing_role_to == "owner":
            return
        stmt = select(func.count()).select_from(User).where(
            User.organization_id == user.organization_id,
            User.role_id == owner_role.id,
            User.is_active.is_(True),
            User.deleted_at.is_(None),
        )
        active_owners = (await self.db.execute(stmt)).scalar_one()
        if active_owners <= 1:
            raise ValidationAppError(
                "This is the last active Owner in the organization. "
                "Promote another user to Owner first."
            )

    # -- Group assignment (Supervisor scoping) ---------------------------
    async def assign_group(
        self, payload: UserGroupAssignmentCreate, organization_id: uuid.UUID
    ) -> None:
        user = await self.get_user_or_404(payload.user_id, organization_id)
        group = await self._resolve_group_in_org(payload.group_id, organization_id)

        region = await self.regions.get(group.region_id)
        if not region or region.organization_id != user.organization_id:
            raise ValidationAppError("Group does not belong to the user's organization.")

        existing = await self.users.get_assignment(payload.user_id, payload.group_id)
        if existing:
            raise DuplicateError("This user is already assigned to this group.")

        self.users.add_assignment(payload.user_id, payload.group_id)
        await self.audit.record(
            actor_id=None, action="user.assign_group", entity_type="user", entity_id=user.id,
            after={"group_id": str(payload.group_id)},
        )
        await self.users.commit()

    async def unassign_group(
        self, user_id: uuid.UUID, group_id: uuid.UUID, organization_id: uuid.UUID
    ) -> None:
        await self.get_user_or_404(user_id, organization_id)
        assignment = await self.users.get_assignment(user_id, group_id)
        if not assignment:
            raise NotFoundError("Assignment not found.")
        await self.users.remove_assignment(assignment)
        await self.audit.record(
            actor_id=None, action="user.unassign_group", entity_type="user", entity_id=user_id,
            before={"group_id": str(group_id)},
        )
        await self.users.commit()

    async def _resolve_group_in_org(self, group_id: uuid.UUID, organization_id: uuid.UUID) -> Group:
        stmt = (
            select(Group)
            .join(Region, Group.region_id == Region.id)
            .where(
                Group.id == group_id,
                Region.organization_id == organization_id,
                Group.deleted_at.is_(None),
            )
        )
        group = (await self.db.execute(stmt)).scalar_one_or_none()
        if not group:
            raise NotFoundError("Group not found.")
        return group
