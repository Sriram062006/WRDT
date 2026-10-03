from __future__ import annotations

import uuid
from datetime import date

from pydantic import BaseModel, Field

from app.schemas.base import TimestampedRead


class GroupCreate(BaseModel):
    # region_id comes from the path (/regions/{region_id}/groups); accepting
    # it in the body too invited a mismatch where the body value was silently
    # ignored.
    name: str = Field(..., min_length=1, max_length=200)
    formed_date: date | None = None


class GroupUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=200)
    status: str | None = None


class GroupRead(TimestampedRead):
    region_id: uuid.UUID
    name: str
    formed_date: date
    status: str


class GroupWithCounts(GroupRead):
    members_count: int = 0
