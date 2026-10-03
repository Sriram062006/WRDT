from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field

from app.schemas.base import TimestampedRead


class MemberCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    phone: str | None = Field(None, max_length=20)
    joined_date: date | None = None
    # Bootstrap-only seed values (see Member model docstring) -- only ever
    # read to build meeting #1's opening balances, never touched again.
    seed_prev_saving: Decimal = Field(Decimal("0"), ge=0)
    seed_loan: Decimal = Field(Decimal("0"), ge=0)
    seed_install: Decimal = Field(Decimal("0"), ge=0)
    seed_fine: Decimal = Field(Decimal("0"), ge=0)


class MemberUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=200)
    phone: str | None = Field(None, max_length=20)
    status: str | None = None
    seed_prev_saving: Decimal | None = Field(None, ge=0)


class MemberRead(TimestampedRead):
    group_id: uuid.UUID
    code: str
    name: str
    phone: str | None
    joined_date: date
    status: str
    seed_prev_saving: Decimal
    seed_loan: Decimal
    seed_install: Decimal
    seed_fine: Decimal


class MemberWithGroup(MemberRead):
    """Flat member-list rows need their group/region labels; without them
    the client would have to resolve each parent name separately."""

    group_name: str
    region_id: uuid.UUID
    region_name: str
