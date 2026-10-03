"""
Meeting / MeetingEntry / Expense repositories.

Carry-forward and lock-enforcement logic does NOT live here -- these
repositories only provide the raw queries that meeting_service composes:
fetch the group's meetings in order, fetch one meeting's entries, etc. The
permanent lock itself is enforced at the database level by triggers (see
migrations/versions/0003_partial_indexes_and_triggers.py); the service
layer additionally checks `meeting.locked` before writing so the API can
return a clean 409 (MeetingLockedError) instead of surfacing a raw
database trigger exception.
"""
from __future__ import annotations

import uuid

from sqlalchemy import Integer, case, func, select
from sqlalchemy.orm import selectinload

from app.models.expense import Expense
from app.models.meeting import Meeting
from app.models.meeting_entry import MeetingEntry
from app.repositories.base import BaseRepository


class MeetingRepository(BaseRepository[Meeting]):
    model = Meeting

    async def get_open_meeting_for_group(self, group_id: uuid.UUID) -> Meeting | None:
        stmt = select(Meeting).where(Meeting.group_id == group_id, Meeting.status == "in_progress")
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_last_meeting_for_group(self, group_id: uuid.UUID) -> Meeting | None:
        stmt = (
            select(Meeting)
            .where(Meeting.group_id == group_id)
            .order_by(Meeting.meeting_no.desc())
            .limit(1)
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_group(
        self, group_id: uuid.UUID, *, offset: int = 0, limit: int = 20
    ) -> list[Meeting]:
        stmt = (
            select(Meeting)
            .where(Meeting.group_id == group_id)
            .order_by(Meeting.meeting_no.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def count_by_group(self, group_id: uuid.UUID) -> int:
        stmt = select(func.count()).select_from(Meeting).where(Meeting.group_id == group_id)
        result = await self.db.execute(stmt)
        return result.scalar_one()

    async def list_by_group_with_totals(
        self, group_id: uuid.UUID, *, offset: int = 0, limit: int = 20
    ) -> list[dict]:
        """
        Meetings plus their headline totals, aggregated by the database.

        Rendering the Meetings List used to mean loading every ledger row
        of every meeting and summing them in Python -- N+1 round trips and
        a large payload for a screen that shows six numbers per row. The
        expressions below are the same formulas `ledger_engine` uses, so a
        list row can never disagree with the register it links to.
        """
        entry_agg = (
            select(
                MeetingEntry.meeting_id.label("meeting_id"),
                func.coalesce(func.sum(MeetingEntry.cur_saving), 0).label("total_saving"),
                func.coalesce(func.sum(MeetingEntry.loan_given), 0).label("total_loan"),
                func.coalesce(
                    func.sum(
                        MeetingEntry.cur_saving
                        + MeetingEntry.principal_paid
                        + MeetingEntry.fine
                        + MeetingEntry.interest_paid
                    ),
                    0,
                ).label("total_cash_coll"),
                func.coalesce(func.sum(case((MeetingEntry.present.is_(True), 1), else_=0)), 0)
                .cast(Integer)
                .label("members_present"),
                func.count(MeetingEntry.id).cast(Integer).label("members_total"),
            )
            .group_by(MeetingEntry.meeting_id)
            .subquery()
        )

        expense_agg = (
            select(
                Expense.meeting_id.label("meeting_id"),
                func.coalesce(func.sum(Expense.amount), 0).label("total_expense"),
            )
            .group_by(Expense.meeting_id)
            .subquery()
        )

        stmt = (
            select(
                Meeting.id,
                Meeting.group_id,
                Meeting.meeting_no,
                Meeting.meeting_date,
                Meeting.status,
                Meeting.locked,
                Meeting.supervisor_id,
                func.coalesce(entry_agg.c.total_saving, 0).label("total_saving"),
                func.coalesce(entry_agg.c.total_loan, 0).label("total_loan"),
                func.coalesce(entry_agg.c.total_cash_coll, 0).label("total_cash_coll"),
                func.coalesce(entry_agg.c.members_present, 0).label("members_present"),
                func.coalesce(entry_agg.c.members_total, 0).label("members_total"),
                func.coalesce(expense_agg.c.total_expense, 0).label("total_expense"),
            )
            .select_from(Meeting)
            .outerjoin(entry_agg, entry_agg.c.meeting_id == Meeting.id)
            .outerjoin(expense_agg, expense_agg.c.meeting_id == Meeting.id)
            .where(Meeting.group_id == group_id)
            .order_by(Meeting.meeting_no.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        return [dict(row._mapping) for row in result.all()]

    async def get_with_entries_and_expenses(self, meeting_id: uuid.UUID) -> Meeting | None:
        stmt = (
            select(Meeting)
            .where(Meeting.id == meeting_id)
            .options(selectinload(Meeting.entries), selectinload(Meeting.expenses))
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()


class MeetingEntryRepository(BaseRepository[MeetingEntry]):
    model = MeetingEntry

    async def list_by_meeting(self, meeting_id: uuid.UUID) -> list[MeetingEntry]:
        """Ordered by member code so the on-screen register, the Excel
        export and the printed sheet all show rows in the same order as
        the paper book."""
        from app.models.member import Member

        stmt = (
            select(MeetingEntry)
            .join(Member, MeetingEntry.member_id == Member.id)
            .where(MeetingEntry.meeting_id == meeting_id)
            .order_by(Member.code.asc())
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_by_meeting_and_member(
        self, meeting_id: uuid.UUID, member_id: uuid.UUID
    ) -> MeetingEntry | None:
        stmt = select(MeetingEntry).where(
            MeetingEntry.meeting_id == meeting_id, MeetingEntry.member_id == member_id
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_id_and_meeting(
        self, entry_id: uuid.UUID, meeting_id: uuid.UUID
    ) -> MeetingEntry | None:
        stmt = select(MeetingEntry).where(
            MeetingEntry.id == entry_id, MeetingEntry.meeting_id == meeting_id
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()


class ExpenseRepository(BaseRepository[Expense]):
    model = Expense

    async def list_by_meeting(self, meeting_id: uuid.UUID) -> list[Expense]:
        stmt = (
            select(Expense)
            .where(Expense.meeting_id == meeting_id)
            .order_by(Expense.created_at.asc())
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_by_id_and_meeting(
        self, expense_id: uuid.UUID, meeting_id: uuid.UUID
    ) -> Expense | None:
        stmt = select(Expense).where(Expense.id == expense_id, Expense.meeting_id == meeting_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()
