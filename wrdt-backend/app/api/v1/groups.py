"""
Groups CRUD.

Three routers are exposed from this module:
  - `nested_router` -> /regions/{region_id}/groups  (list, create)
  - `flat_router`   -> /groups                       (org-wide list)
  - `router`        -> /groups/{group_id}            (get, update, delete)

The org-wide flat list exists because the UI has an "all groups across
regions" screen; without it the client would have to fan out one request
per region and paginate them itself.

Create/Update/Delete are Owner-only. Read is available to Owners
(unrestricted within their own organization) and Supervisors (scoped to
their assignments) -- both enforced server-side by
`access.assert_group_access`, never by the UI only.
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, status

from app.api.deps import CurrentUserDep, DbSession, PageParamsDep, require_role
from app.schemas.base import Page
from app.schemas.group import GroupCreate, GroupUpdate, GroupWithCounts
from app.services import access
from app.services.group_service import GroupService

nested_router = APIRouter()
flat_router = APIRouter()
router = APIRouter()


@nested_router.get("", response_model=Page[GroupWithCounts], summary="List groups in a region")
async def list_groups(
    region_id: uuid.UUID,
    db: DbSession,
    page_params: PageParamsDep,
    current_user: CurrentUserDep,
):
    # Tenant check on the parent region first: a region outside the
    # caller's organization must 404 rather than return an empty page,
    # which would leak that the ID is well-formed but foreign.
    await access.resolve_region(db, current_user, region_id)
    service = GroupService(db)
    allowed = None if current_user.role_name == "owner" else set(current_user.assigned_group_ids)
    items, total = await service.list_groups(
        region_id,
        offset=page_params.offset,
        limit=page_params.page_size,
        q=page_params.q,
        allowed_group_ids=allowed,
    )
    return Page(items=items, total=total, page=page_params.page, page_size=page_params.page_size)


@flat_router.get("", response_model=Page[GroupWithCounts], summary="List all groups I can see")
async def list_all_groups(
    db: DbSession,
    page_params: PageParamsDep,
    current_user: CurrentUserDep,
    region_id: uuid.UUID | None = Query(None),
):
    if region_id is not None:
        await access.resolve_region(db, current_user, region_id)
    service = GroupService(db)
    allowed = None if current_user.role_name == "owner" else set(current_user.assigned_group_ids)
    items, total = await service.list_groups_for_org(
        current_user.organization_id,
        offset=page_params.offset,
        limit=page_params.page_size,
        q=page_params.q,
        region_id=region_id,
        allowed_group_ids=allowed,
    )
    return Page(items=items, total=total, page=page_params.page, page_size=page_params.page_size)


@nested_router.post(
    "",
    response_model=GroupWithCounts,
    status_code=status.HTTP_201_CREATED,
    summary="Create group",
    dependencies=[Depends(require_role("owner"))],
)
async def create_group(
    region_id: uuid.UUID, payload: GroupCreate, db: DbSession, current_user: CurrentUserDep
):
    await access.resolve_region(db, current_user, region_id)
    service = GroupService(db)
    group = await service.create_group(region_id, payload, current_user.id)
    return await service.get_with_counts(group.id)


@router.get("/{group_id}", response_model=GroupWithCounts, summary="Get group")
async def get_group(group_id: uuid.UUID, db: DbSession, current_user: CurrentUserDep):
    await access.assert_group_access(db, current_user, group_id)
    service = GroupService(db)
    return await service.get_with_counts(group_id)


@router.put(
    "/{group_id}",
    response_model=GroupWithCounts,
    summary="Update group",
    dependencies=[Depends(require_role("owner"))],
)
async def update_group(
    group_id: uuid.UUID, payload: GroupUpdate, db: DbSession, current_user: CurrentUserDep
):
    await access.resolve_group(db, current_user, group_id)
    service = GroupService(db)
    await service.update_group(group_id, payload, current_user.id)
    return await service.get_with_counts(group_id)


@router.delete(
    "/{group_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete group (cascades)",
    dependencies=[Depends(require_role("owner"))],
)
async def delete_group(group_id: uuid.UUID, db: DbSession, current_user: CurrentUserDep):
    await access.resolve_group(db, current_user, group_id)
    service = GroupService(db)
    await service.delete_group(group_id, current_user.id)
