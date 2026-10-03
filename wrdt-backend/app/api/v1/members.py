"""
Members CRUD.

Three routers, same pattern as groups.py:
  - `nested_router` -> /groups/{group_id}/members (list, create)
  - `flat_router`   -> /members                    (org-wide list)
  - `router`        -> /members/{member_id}        (get, update, delete)

Member CRUD is Owner-only. Supervisors may READ members within groups
they're assigned to (they need this to run meetings). Both the tenant and
the supervisor-scope checks happen in `app.services.access`.
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, status

from app.api.deps import CurrentUserDep, DbSession, PageParamsDep, require_role
from app.schemas.base import Page
from app.schemas.member import MemberCreate, MemberRead, MemberUpdate, MemberWithGroup
from app.services import access
from app.services.member_service import MemberService

nested_router = APIRouter()
flat_router = APIRouter()
router = APIRouter()


@nested_router.get("", response_model=Page[MemberRead], summary="List members in a group")
async def list_members(
    group_id: uuid.UUID,
    db: DbSession,
    page_params: PageParamsDep,
    current_user: CurrentUserDep,
):
    await access.assert_group_access(db, current_user, group_id)
    service = MemberService(db)
    members, total = await service.list_members(
        group_id, offset=page_params.offset, limit=page_params.page_size, q=page_params.q
    )
    return Page(
        items=[MemberRead.model_validate(m) for m in members],
        total=total,
        page=page_params.page,
        page_size=page_params.page_size,
    )


@flat_router.get("", response_model=Page[MemberWithGroup], summary="List all members I can see")
async def list_all_members(
    db: DbSession,
    page_params: PageParamsDep,
    current_user: CurrentUserDep,
    group_id: uuid.UUID | None = Query(None),
    region_id: uuid.UUID | None = Query(None),
):
    if group_id is not None:
        await access.assert_group_access(db, current_user, group_id)
    if region_id is not None:
        await access.resolve_region(db, current_user, region_id)
    allowed = None if current_user.role_name == "owner" else set(current_user.assigned_group_ids)
    service = MemberService(db)
    items, total = await service.list_members_for_org(
        current_user.organization_id,
        offset=page_params.offset,
        limit=page_params.page_size,
        q=page_params.q,
        group_id=group_id,
        region_id=region_id,
        allowed_group_ids=allowed,
    )
    return Page(items=items, total=total, page=page_params.page, page_size=page_params.page_size)


@nested_router.post(
    "",
    response_model=MemberRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create member",
    dependencies=[Depends(require_role("owner"))],
)
async def create_member(
    group_id: uuid.UUID, payload: MemberCreate, db: DbSession, current_user: CurrentUserDep
):
    await access.resolve_group(db, current_user, group_id)
    service = MemberService(db)
    member = await service.create_member(group_id, payload, current_user.id)
    return MemberRead.model_validate(member)


@router.get("/{member_id}", response_model=MemberRead, summary="Get member")
async def get_member(member_id: uuid.UUID, db: DbSession, current_user: CurrentUserDep):
    member = await access.resolve_member(db, current_user, member_id)
    return MemberRead.model_validate(member)


@router.put(
    "/{member_id}",
    response_model=MemberRead,
    summary="Update member",
    dependencies=[Depends(require_role("owner"))],
)
async def update_member(
    member_id: uuid.UUID, payload: MemberUpdate, db: DbSession, current_user: CurrentUserDep
):
    await access.resolve_member(db, current_user, member_id)
    service = MemberService(db)
    member = await service.update_member(member_id, payload, current_user.id)
    return MemberRead.model_validate(member)


@router.delete(
    "/{member_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete member",
    dependencies=[Depends(require_role("owner"))],
)
async def delete_member(member_id: uuid.UUID, db: DbSession, current_user: CurrentUserDep):
    await access.resolve_member(db, current_user, member_id)
    service = MemberService(db)
    await service.delete_member(member_id, current_user.id)
