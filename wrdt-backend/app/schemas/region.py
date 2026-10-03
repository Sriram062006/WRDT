from __future__ import annotations

import uuid

from pydantic import BaseModel, Field

from app.schemas.base import TimestampedRead


class RegionCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)


class RegionUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=200)
    status: str | None = None


class RegionRead(TimestampedRead):
    organization_id: uuid.UUID
    name: str
    status: str


class RegionWithCounts(RegionRead):
    """Matches the frontend's REGIONS array shape, which carries denormalized
    `groups`/`members` counts alongside each region for the list screen."""

    groups_count: int = 0
    members_count: int = 0
