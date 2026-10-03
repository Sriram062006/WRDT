"""
User management routes -- Owner-only (User Management is explicitly an
Owner-only permission; Supervisors cannot reach any route in this file,
enforced by `require_role("owner")` on the router).

Every route is additionally scoped to the caller's own organization. The
previous version looked users up by bare ID and created them with a
client-supplied `organization_id`, which let an Owner read, edit,
deactivate, or mint users inside a different tenant.
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, status

from app.api.deps import CurrentUserDep, DbSession, PageParamsDep, require_role
from app.schemas.base import Page
from app.schemas.role import RoleRead
from app.schemas.user import UserCreate, UserGroupAssignmentCreate, UserRead, UserUpdate
from app.services.user_service import UserService

router = APIRouter(dependencies=[Depends(require_role("owner"))])


@router.get("", response_model=Page[UserRead], summary="List users in my organization")
async def list_users(db: DbSession, page_params: PageParamsDep, current_user: CurrentUserDep):
    service = UserService(db)
    users = await service.list_users(
        current_user.organization_id, offset=page_params.offset, limit=page_params.page_size
    )
    # Previously this returned a global user count, so a single-user
    # organization could be told it had every user on the platform.
    total = await service.count_users(current_user.organization_id)
    return Page(
        items=[UserRead.model_validate(u) for u in users],
        total=total,
        page=page_params.page,
        page_size=page_params.page_size,
    )


@router.get("/roles", response_model=list[RoleRead], summary="List assignable roles")
async def list_roles(db: DbSession):
    """The Create-User form needs real role IDs; hard-coding them in the
    client would break the moment roles are re-seeded."""
    service = UserService(db)
    roles = await service.list_roles()
    return [RoleRead.model_validate(r) for r in roles]


@router.post("", response_model=UserRead, status_code=status.HTTP_201_CREATED, summary="Create user")
async def create_user(payload: UserCreate, db: DbSession, current_user: CurrentUserDep):
    service = UserService(db)
    user = await service.create_user(current_user.organization_id, payload)
    return UserRead.model_validate(user)


@router.get("/{user_id}", response_model=UserRead, summary="Get user")
async def get_user(user_id: uuid.UUID, db: DbSession, current_user: CurrentUserDep):
    service = UserService(db)
    user = await service.get_user_or_404(user_id, current_user.organization_id)
    return UserRead.model_validate(user)


@router.put("/{user_id}", response_model=UserRead, summary="Update user / change role")
async def update_user(
    user_id: uuid.UUID, payload: UserUpdate, db: DbSession, current_user: CurrentUserDep
):
    service = UserService(db)
    user = await service.update_user(user_id, payload, current_user)
    return UserRead.model_validate(user)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Deactivate user")
async def deactivate_user(user_id: uuid.UUID, db: DbSession, current_user: CurrentUserDep):
    service = UserService(db)
    await service.deactivate_user(user_id, current_user)


@router.get(
    "/{user_id}/group-assignments",
    response_model=list[uuid.UUID],
    summary="List a Supervisor's assigned group IDs",
)
async def list_group_assignments(user_id: uuid.UUID, db: DbSession, current_user: CurrentUserDep):
    service = UserService(db)
    await service.get_user_or_404(user_id, current_user.organization_id)
    return await service.list_assignments(user_id)


@router.post(
    "/group-assignments",
    status_code=status.HTTP_201_CREATED,
    summary="Assign a Supervisor to a Group",
)
async def assign_group(
    payload: UserGroupAssignmentCreate, db: DbSession, current_user: CurrentUserDep
):
    service = UserService(db)
    await service.assign_group(payload, current_user.organization_id)
    return {"status": "assigned"}


@router.delete(
    "/{user_id}/group-assignments/{group_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Unassign a Supervisor from a Group",
)
async def unassign_group(
    user_id: uuid.UUID, group_id: uuid.UUID, db: DbSession, current_user: CurrentUserDep
):
    service = UserService(db)
    await service.unassign_group(user_id, group_id, current_user.organization_id)
