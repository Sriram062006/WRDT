"""
Expense — a single line item of a meeting's expenses (Travel / Tea /
Stationery / Others / custom), matching the frontend's DEFAULT_EXPENSES /
per-meeting expenses array. Contributes to Cash in Hand
(cash_in_hand = totCashColl - totExpense - totLoan) via the ledger engine,
never computed here.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

import uuid

from sqlalchemy import ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPKMixin



if TYPE_CHECKING:  # pragma: no cover - import cycle guard for relationship types
    from app.models.meeting import Meeting

class Expense(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "expenses"

    meeting_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("meetings.id"), nullable=False
    )
    expense_type: Mapped[str] = mapped_column(String(50), nullable=False)  # Travel|Tea|Stationery|Others|custom
    amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, default=0)

    meeting: Mapped["Meeting"] = relationship(back_populates="expenses")
