"""
Regions CRUD -- Owner-only end to end (Regions are not in the Supervisor
permission set at all: Supervisors work at the Group level via "View
Assigned Groups", never at the Region level).

Every by-ID route resolves the region through `access.resolve_region`,
which scopes the lookup to the caller's organization. Fetching by bare ID
would let an Owner of one tenant read/modify another tenant's regions.
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, status

from app.api.deps import CurrentUserDep, DbSession, PageParamsDep, require_role
from app.schemas.base import Page
from app.schemas.region import RegionCreate, RegionUpdate, RegionWithCounts
from app.services import access
from app.services.region_service import RegionService

router = APIRouter(dependencies=[Depends(require_role("owner"))])


@router.get("", response_model=Page[RegionWithCounts], summary="List regions")
async def list_regions(db: DbSession, page_params: PageParamsDep, current_user: CurrentUserDep):
    service = RegionService(db)
    items, total = await service.list_regions(
        current_user.organization_id,
        offset=page_params.offset,
        limit=page_params.page_size,
        q=page_params.q,
    )
    return Page(items=items, total=total, page=page_params.page, page_size=page_params.page_size)


@router.post(
    "", response_model=RegionWithCounts, status_code=status.HTTP_201_CREATED, summary="Create region"
)
async def create_region(payload: RegionCreate, db: DbSession, current_user: CurrentUserDep):
    service = RegionService(db)
    region = await service.create_region(current_user.organization_id, payload, current_user.id)
    return await service.get_with_counts(region.id)


@router.get("/{region_id}", response_model=RegionWithCounts, summary="Get region")
async def get_region(region_id: uuid.UUID, db: DbSession, current_user: CurrentUserDep):
    await access.resolve_region(db, current_user, region_id)
    service = RegionService(db)
    return await service.get_with_counts(region_id)


@router.put("/{region_id}", response_model=RegionWithCounts, summary="Update region")
async def update_region(
    region_id: uuid.UUID, payload: RegionUpdate, db: DbSession, current_user: CurrentUserDep
):
    await access.resolve_region(db, current_user, region_id)
    service = RegionService(db)
    await service.update_region(region_id, payload, current_user.id)
    return await service.get_with_counts(region_id)


@router.delete(
    "/{region_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete region (cascades)"
)
async def delete_region(region_id: uuid.UUID, db: DbSession, current_user: CurrentUserDep):
    await access.resolve_region(db, current_user, region_id)
    service = RegionService(db)
    await service.delete_region(region_id, current_user.id)
