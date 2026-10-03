from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.base import TimestampedRead


class OrganizationCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)


class OrganizationUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=200)
    status: str | None = None


class OrganizationRead(TimestampedRead):
    name: str
    status: str
