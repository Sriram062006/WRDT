"""
Aggregates all v1 routers under a single APIRouter, mounted once in main.py
under settings.API_V1_PREFIX.
"""
from fastapi import APIRouter

from app.api.v1 import auth, excel_import, groups, health, meetings, members, regions, reports, users

api_router = APIRouter()

api_router.include_router(health.router)
api_router.include_router(auth.router, prefix="/auth", tags=["Auth"])
api_router.include_router(users.router, prefix="/users", tags=["User Management"])

api_router.include_router(regions.router, prefix="/regions", tags=["Regions"])
api_router.include_router(groups.nested_router, prefix="/regions/{region_id}/groups", tags=["Groups"])
api_router.include_router(groups.flat_router, prefix="/groups", tags=["Groups"])
api_router.include_router(groups.router, prefix="/groups", tags=["Groups"])
api_router.include_router(members.nested_router, prefix="/groups/{group_id}/members", tags=["Members"])
api_router.include_router(members.flat_router, prefix="/members", tags=["Members"])
api_router.include_router(members.router, prefix="/members", tags=["Members"])
api_router.include_router(meetings.nested_router, prefix="/groups/{group_id}/meetings", tags=["Meetings"])
api_router.include_router(meetings.router, prefix="/meetings", tags=["Meetings"])
api_router.include_router(excel_import.router, prefix="/import", tags=["Excel Import"])
api_router.include_router(reports.router, prefix="/reports", tags=["Reports"])
