from __future__ import annotations

from pydantic import BaseModel

from app.schemas.base import TimestampedRead


class RoleRead(TimestampedRead):
    name: str
    description: str | None
    permissions: dict


class RoleCreate(BaseModel):
    name: str
    description: str | None = None
    permissions: dict = {}
