"""
Health check endpoint(s) — used by load balancers, uptime monitors, and
container orchestrators (e.g. ECS/Cloud Run readiness & liveness probes).
"""
from __future__ import annotations

from fastapi import APIRouter, status
from sqlalchemy import text

from app.api.deps import DbSession
from app.core.config import get_settings

router = APIRouter(tags=["Health"])


@router.get("/health", status_code=status.HTTP_200_OK, summary="Liveness check")
async def health() -> dict:
    """Process is up. Does not touch the database — for fast liveness probes."""
    settings = get_settings()
    return {"status": "ok", "app": settings.APP_NAME, "env": settings.APP_ENV}


@router.get("/health/ready", status_code=status.HTTP_200_OK, summary="Readiness check")
async def readiness(db: DbSession) -> dict:
    """Process is up AND can reach the database — for readiness probes."""
    await db.execute(text("SELECT 1"))
    return {"status": "ready", "database": "connected"}
