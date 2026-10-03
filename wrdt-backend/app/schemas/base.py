"""
Shared Pydantic base classes and pagination envelope used by every schema
module. Keeping ORM-to-schema conversion (`from_attributes=True`) and
timestamp/id typing in one place avoids config drift between entities.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict

T = TypeVar("T")


class ORMBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class TimestampedRead(ORMBase):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int
