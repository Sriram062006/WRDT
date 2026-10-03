from __future__ import annotations

import uuid
from decimal import Decimal

from pydantic import BaseModel, Field

from app.schemas.base import TimestampedRead


class ExpenseCreate(BaseModel):
    expense_type: str = Field(..., min_length=1, max_length=50)
    amount: Decimal = Field(Decimal("0"), ge=0)


class ExpenseUpdate(BaseModel):
    expense_type: str | None = Field(None, min_length=1, max_length=50)
    amount: Decimal | None = Field(None, ge=0)


class ExpenseRead(TimestampedRead):
    meeting_id: uuid.UUID
    expense_type: str
    amount: Decimal
