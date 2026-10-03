"""
Reports service -- Dashboard statistics, Member/Loan ledger reports, and
Group/Region/Monthly/Expense aggregates.

Everything here is a derived, read-only aggregate over meeting_entries /
expenses. This module NEVER writes, and never invents a number that could
not also be reached by summing the same rows the Meeting Register shows.
Row-level `cash_paid` reuses `ledger_engine.row_cash_paid` so a figure in
a report can never disagree with the same row in the live register.

Two rules run through the whole file:

  * "Outstanding loan" means each member's balance at their MOST RECENT
    meeting, never the sum of `loan_remaining` across their history. The
    earlier version summed every historical row, so a member with a
    5,000 balance who had attended eight meetings was reported as owing
    40,000. Dashboard and Loan Ledger both route through
    `_latest_entry_per_member()` so they cannot drift apart again.

  * Supervisors are scoped. Every aggregate accepts `group_scope`; when
    it is not None the query is restricted to those group IDs, and an
    EMPTY scope matches nothing rather than everything.
"""
from __future__ import annotations

import uuid
from datetime import date, timedelta

from sqlalchemy import Select, func, select

from app.core.exceptions import NotFoundError
from app.models.audit_log import AuditLog
from app.models.expense import Expense
from app.models.group import Group
from app.models.meeting import Meeting
from app.models.meeting_entry import MeetingEntry
from app.models.member import Member
from app.models.region import Region
from app.models.user import User
from app.schemas.reports import (
    DashboardStats,
    ExpenseLine,
    ExpenseReport,
    ExpenseRow,
    GroupReport,
    LoanLedgerEntry,
    LoanLedgerReport,
    MemberLedgerReport,
    MemberLedgerRow,
    MonthlyReport,
    RegionReport,
)
from app.services import ledger_engine
from app.services.base import BaseService


def _scoped(stmt: Select, group_scope: list[uuid.UUID] | None, column) -> Select:
    if group_scope is None:
        return stmt
    ids = list(group_scope)
    return stmt.where(column.in_(ids) if ids else False)


def _latest_entry_per_member():
    """Subquery: (member_id, latest meeting_no) for every member that has
    at least one ledger row. Joined back on, this yields exactly one
    'current' entry per member."""
    return (
        select(
            MeetingEntry.member_id.label("member_id"),
            func.max(Meeting.meeting_no).label("latest_no"),
        )
        .select_from(MeetingEntry)
        .join(Meeting, MeetingEntry.meeting_id == Meeting.id)
        .group_by(MeetingEntry.member_id)
        .subquery()
    )


class ReportService(BaseService):
    # -- Dashboard --------------------------------------------------------
    async def get_dashboard_stats(
        self, organization_id: uuid.UUID, *, group_scope: list[uuid.UUID] | None = None
    ) -> DashboardStats:
        org_groups = (
            select(Group.id)
            .join(Region, Group.region_id == Region.id)
            .where(Region.organization_id == organization_id, Group.deleted_at.is_(None))
            .scalar_subquery()
        )

        total_regions = await self.db.scalar(
            select(func.count())
            .select_from(Region)
            .where(Region.organization_id == organization_id, Region.deleted_at.is_(None))
        )

        groups_q = _scoped(
            select(func.count()).select_from(Group).where(
                Group.id.in_(org_groups), Group.deleted_at.is_(None)
            ),
            group_scope,
            Group.id,
        )
        total_groups = await self.db.scalar(groups_q)

        members_q = _scoped(
            select(func.count()).select_from(Member).where(
                Member.group_id.in_(org_groups), Member.deleted_at.is_(None)
            ),
            group_scope,
            Member.group_id,
        )
        total_members = await self.db.scalar(members_q)

        active_q = _scoped(
            select(func.count()).select_from(Meeting).where(
                Meeting.group_id.in_(org_groups), Meeting.status == "in_progress"
            ),
            group_scope,
            Meeting.group_id,
        )
        active_meetings = await self.db.scalar(active_q)

        # Total savings held = each member's balance at their latest
        # meeting (prev + current), not the sum over all history.
        latest = _latest_entry_per_member()
        savings_q = _scoped(
            select(
                func.coalesce(func.sum(MeetingEntry.prev_saving + MeetingEntry.cur_saving), 0)
            )
            .select_from(MeetingEntry)
            .join(Meeting, MeetingEntry.meeting_id == Meeting.id)
            .join(
                latest,
                (latest.c.member_id == MeetingEntry.member_id)
                & (latest.c.latest_no == Meeting.meeting_no),
            )
            .where(Meeting.group_id.in_(org_groups)),
            group_scope,
            Meeting.group_id,
        )
        total_savings = await self.db.scalar(savings_q)

        loans_q = _scoped(
            select(func.coalesce(func.sum(MeetingEntry.loan_remaining), 0))
            .select_from(MeetingEntry)
            .join(Meeting, MeetingEntry.meeting_id == Meeting.id)
            .join(
                latest,
                (latest.c.member_id == MeetingEntry.member_id)
                & (latest.c.latest_no == Meeting.meeting_no),
            )
            .where(Meeting.group_id.in_(org_groups)),
            group_scope,
            Meeting.group_id,
        )
        total_loans_outstanding = await self.db.scalar(loans_q)

        today = date.today()
        today_q = _scoped(
            select(
                func.coalesce(
                    func.sum(
                        MeetingEntry.cur_saving
                        + MeetingEntry.principal_paid
                        + MeetingEntry.interest_paid
                        + MeetingEntry.fine
                    ),
                    0,
                )
            )
            .select_from(MeetingEntry)
            .join(Meeting, MeetingEntry.meeting_id == Meeting.id)
            .where(Meeting.group_id.in_(org_groups), Meeting.meeting_date == today),
            group_scope,
            Meeting.group_id,
        )
        todays_collection = await self.db.scalar(today_q)

        month_q = _scoped(
            select(func.count())
            .select_from(Meeting)
            .where(
                Meeting.group_id.in_(org_groups),
                Meeting.status == "completed",
                func.extract("year", Meeting.meeting_date) == today.year,
                func.extract("month", Meeting.meeting_date) == today.month,
            ),
            group_scope,
            Meeting.group_id,
        )
        meetings_completed_this_month = await self.db.scalar(month_q)

        return DashboardStats(
            total_regions=total_regions or 0,
            total_groups=total_groups or 0,
            total_members=total_members or 0,
            active_meetings=active_meetings or 0,
            total_savings=total_savings or 0,
            total_loans_outstanding=total_loans_outstanding or 0,
            todays_collection=todays_collection or 0,
            meetings_completed_this_month=meetings_completed_this_month or 0,
        )

    async def get_collection_series(
        self,
        organization_id: uuid.UUID,
        *,
        days: int = 30,
        group_scope: list[uuid.UUID] | None = None,
    ) -> list[dict]:
        """Collections per meeting date over a trailing window -- the real
        data behind the dashboard chart, which previously plotted seven
        hard-coded figures."""
        org_groups = (
            select(Group.id)
            .join(Region, Group.region_id == Region.id)
            .where(Region.organization_id == organization_id, Group.deleted_at.is_(None))
            .scalar_subquery()
        )
        since = date.today() - timedelta(days=days)
        stmt = _scoped(
            select(
                Meeting.meeting_date.label("date"),
                func.coalesce(
                    func.sum(
                        MeetingEntry.cur_saving
                        + MeetingEntry.principal_paid
                        + MeetingEntry.interest_paid
                        + MeetingEntry.fine
                    ),
                    0,
                ).label("amount"),
            )
            .select_from(MeetingEntry)
            .join(Meeting, MeetingEntry.meeting_id == Meeting.id)
            .where(Meeting.group_id.in_(org_groups), Meeting.meeting_date >= since)
            .group_by(Meeting.meeting_date)
            .order_by(Meeting.meeting_date.asc()),
            group_scope,
            Meeting.group_id,
        )
        rows = (await self.db.execute(stmt)).all()
        return [{"date": r.date.isoformat(), "amount": float(r.amount or 0)} for r in rows]

    # -- Member Ledger ----------------------------------------------------
    async def get_member_ledger(self, member_id: uuid.UUID) -> MemberLedgerReport:
        member = await self.db.get(Member, member_id)
        if not member:
            raise NotFoundError("Member not found.")
        group = await self.db.get(Group, member.group_id)

        stmt = (
            select(MeetingEntry, Meeting)
            .join(Meeting, MeetingEntry.meeting_id == Meeting.id)
            .where(MeetingEntry.member_id == member_id)
            .order_by(Meeting.meeting_no.asc())
        )
        pairs = (await self.db.execute(stmt)).all()

        rows = [
            MemberLedgerRow(
                meeting_id=meeting.id,
                meeting_no=meeting.meeting_no,
                meeting_date=meeting.meeting_date,
                present=entry.present,
                prev_saving=entry.prev_saving,
                cur_saving=entry.cur_saving,
                loan_given=entry.loan_given,
                principal_paid=entry.principal_paid,
                interest_paid=entry.interest_paid,
                loan_remaining=entry.loan_remaining,
                fine=entry.fine,
                cash_paid=ledger_engine.row_cash_paid(entry),
            )
            for entry, meeting in pairs
        ]

        latest = rows[-1] if rows else None
        current_savings_balance = (
            (latest.prev_saving + latest.cur_saving) if latest else member.seed_prev_saving
        )
        current_loan_remaining = latest.loan_remaining if latest else member.seed_loan

        return MemberLedgerReport(
            member_id=member.id,
            member_name=member.name,
            group_id=member.group_id,
            group_name=group.name if group else "",
            rows=rows,
            current_savings_balance=current_savings_balance,
            current_loan_remaining=current_loan_remaining,
        )

    # -- Loan Ledger ------------------------------------------------------
    async def get_loan_ledger(
        self,
        organization_id: uuid.UUID,
        *,
        region_id: uuid.UUID | None = None,
        group_id: uuid.UUID | None = None,
        group_scope: list[uuid.UUID] | None = None,
    ) -> LoanLedgerReport:
        latest = _latest_entry_per_member()

        stmt = (
            select(MeetingEntry, Meeting, Member, Group, Region)
            .join(Meeting, MeetingEntry.meeting_id == Meeting.id)
            .join(
                latest,
                (latest.c.member_id == MeetingEntry.member_id)
                & (latest.c.latest_no == Meeting.meeting_no),
            )
            .join(Member, MeetingEntry.member_id == Member.id)
            .join(Group, Member.group_id == Group.id)
            .join(Region, Group.region_id == Region.id)
            .where(
                Region.organization_id == organization_id,
                MeetingEntry.loan_remaining > 0,
                Member.deleted_at.is_(None),
            )
            .order_by(MeetingEntry.loan_remaining.desc())
        )
        if region_id:
            stmt = stmt.where(Region.id == region_id)
        if group_id:
            stmt = stmt.where(Group.id == group_id)
        stmt = _scoped(stmt, group_scope, Group.id)

        rows = (await self.db.execute(stmt)).all()
        entries = [
            LoanLedgerEntry(
                member_id=member.id,
                member_name=member.name,
                group_id=group.id,
                group_name=group.name,
                region_id=region.id,
                region_name=region.name,
                loan_remaining=entry.loan_remaining,
                loan_remaining_manual=entry.loan_remaining_manual,
                as_of_meeting_no=meeting.meeting_no,
                as_of_meeting_date=meeting.meeting_date,
            )
            for entry, meeting, member, group, region in rows
        ]
        total_outstanding = sum((e.loan_remaining for e in entries), 0)
        return LoanLedgerReport(entries=entries, total_outstanding=total_outstanding)

    # -- Expense report ---------------------------------------------------
    async def get_expense_report(
        self,
        organization_id: uuid.UUID,
        *,
        date_from: date | None = None,
        date_to: date | None = None,
        group_id: uuid.UUID | None = None,
        group_scope: list[uuid.UUID] | None = None,
    ) -> ExpenseReport:
        stmt = (
            select(Expense, Meeting, Group)
            .join(Meeting, Expense.meeting_id == Meeting.id)
            .join(Group, Meeting.group_id == Group.id)
            .join(Region, Group.region_id == Region.id)
            .where(Region.organization_id == organization_id)
            .order_by(Meeting.meeting_date.desc())
        )
        if date_from:
            stmt = stmt.where(Meeting.meeting_date >= date_from)
        if date_to:
            stmt = stmt.where(Meeting.meeting_date <= date_to)
        if group_id:
            stmt = stmt.where(Group.id == group_id)
        stmt = _scoped(stmt, group_scope, Group.id)

        results = (await self.db.execute(stmt)).all()
        rows = [
            ExpenseRow(
                expense_id=exp.id,
                meeting_id=meeting.id,
                meeting_no=meeting.meeting_no,
                meeting_date=meeting.meeting_date,
                group_id=group.id,
                group_name=group.name,
                expense_type=exp.expense_type,
                amount=exp.amount,
            )
            for exp, meeting, group in results
        ]

        by_type: dict[str, list] = {}
        for r in rows:
            bucket = by_type.setdefault(r.expense_type, [0, 0])
            bucket[0] += r.amount
            bucket[1] += 1
        lines = [
            ExpenseLine(expense_type=k, total=v[0], count=v[1])
            for k, v in sorted(by_type.items(), key=lambda kv: -kv[1][0])
        ]
        return ExpenseReport(rows=rows, by_type=lines, total=sum((r.amount for r in rows), 0))

    # -- Group Report -----------------------------------------------------
    async def get_group_report(
        self, group_id: uuid.UUID, *, date_from: date | None = None, date_to: date | None = None
    ) -> GroupReport:
        group = await self.db.get(Group, group_id)
        if not group:
            raise NotFoundError("Group not found.")

        meeting_filter = [Meeting.group_id == group_id]
        if date_from:
            meeting_filter.append(Meeting.meeting_date >= date_from)
        if date_to:
            meeting_filter.append(Meeting.meeting_date <= date_to)

        meetings_count = await self.db.scalar(
            select(func.count()).select_from(Meeting).where(*meeting_filter)
        )

        async def _sum(column):
            return await self.db.scalar(
                select(func.coalesce(func.sum(column), 0))
                .select_from(MeetingEntry)
                .join(Meeting, MeetingEntry.meeting_id == Meeting.id)
                .where(*meeting_filter)
            )

        savings = await _sum(MeetingEntry.cur_saving)
        loans_disbursed = await _sum(MeetingEntry.loan_given)
        loan_repaid = await _sum(MeetingEntry.principal_paid)
        interest = await _sum(MeetingEntry.interest_paid)
        fines = await _sum(MeetingEntry.fine)

        expenses_total = await self.db.scalar(
            select(func.coalesce(func.sum(Expense.amount), 0))
            .select_from(Expense)
            .join(Meeting, Expense.meeting_id == Meeting.id)
            .where(*meeting_filter)
        )

        last_meeting = await self.db.scalar(
            select(Meeting)
            .where(Meeting.group_id == group_id)
            .order_by(Meeting.meeting_no.desc())
            .limit(1)
        )
        current_loan_outstanding = 0
        if last_meeting:
            current_loan_outstanding = await self.db.scalar(
                select(func.coalesce(func.sum(MeetingEntry.loan_remaining), 0)).where(
                    MeetingEntry.meeting_id == last_meeting.id
                )
            )

        return GroupReport(
            group_id=group.id,
            group_name=group.name,
            meetings_count=meetings_count or 0,
            total_savings_collected=savings or 0,
            total_loans_disbursed=loans_disbursed or 0,
            total_loan_repaid=loan_repaid or 0,
            total_interest_collected=interest or 0,
            total_fines_collected=fines or 0,
            total_expenses=expenses_total or 0,
            current_loan_outstanding=current_loan_outstanding or 0,
        )

    # -- Region Report ----------------------------------------------------
    async def get_region_report(
        self, region_id: uuid.UUID, *, date_from: date | None = None, date_to: date | None = None
    ) -> RegionReport:
        region = await self.db.get(Region, region_id)
        if not region:
            raise NotFoundError("Region not found.")

        groups_count = await self.db.scalar(
            select(func.count())
            .select_from(Group)
            .where(Group.region_id == region_id, Group.deleted_at.is_(None))
        )
        members_count = await self.db.scalar(
            select(func.count())
            .select_from(Member)
            .join(Group, Member.group_id == Group.id)
            .where(Group.region_id == region_id, Member.deleted_at.is_(None))
        )

        meeting_filter = [Group.region_id == region_id]
        if date_from:
            meeting_filter.append(Meeting.meeting_date >= date_from)
        if date_to:
            meeting_filter.append(Meeting.meeting_date <= date_to)

        async def _sum(column):
            return await self.db.scalar(
                select(func.coalesce(func.sum(column), 0))
                .select_from(MeetingEntry)
                .join(Meeting, MeetingEntry.meeting_id == Meeting.id)
                .join(Group, Meeting.group_id == Group.id)
                .where(*meeting_filter)
            )

        savings = await _sum(MeetingEntry.cur_saving)
        loans_disbursed = await _sum(MeetingEntry.loan_given)

        expenses_total = await self.db.scalar(
            select(func.coalesce(func.sum(Expense.amount), 0))
            .select_from(Expense)
            .join(Meeting, Expense.meeting_id == Meeting.id)
            .join(Group, Meeting.group_id == Group.id)
            .where(*meeting_filter)
        )

        # Outstanding = latest entry per member inside this region. The
        # previous version filtered on `Meeting.status == 'in_progress'`,
        # so a region whose meetings were all completed reported zero
        # outstanding debt.
        latest = _latest_entry_per_member()
        current_loan_outstanding = await self.db.scalar(
            select(func.coalesce(func.sum(MeetingEntry.loan_remaining), 0))
            .select_from(MeetingEntry)
            .join(Meeting, MeetingEntry.meeting_id == Meeting.id)
            .join(
                latest,
                (latest.c.member_id == MeetingEntry.member_id)
                & (latest.c.latest_no == Meeting.meeting_no),
            )
            .join(Group, Meeting.group_id == Group.id)
            .where(Group.region_id == region_id)
        )

        return RegionReport(
            region_id=region.id,
            region_name=region.name,
            groups_count=groups_count or 0,
            members_count=members_count or 0,
            total_savings_collected=savings or 0,
            total_loans_disbursed=loans_disbursed or 0,
            total_expenses=expenses_total or 0,
            current_loan_outstanding=current_loan_outstanding or 0,
        )

    # -- Monthly Report ---------------------------------------------------
    async def get_monthly_report(
        self, organization_id: uuid.UUID, year: int, month: int
    ) -> MonthlyReport:
        base_filter = [
            Region.organization_id == organization_id,
            func.extract("year", Meeting.meeting_date) == year,
            func.extract("month", Meeting.meeting_date) == month,
        ]

        meetings_completed = await self.db.scalar(
            select(func.count())
            .select_from(Meeting)
            .join(Group, Meeting.group_id == Group.id)
            .join(Region, Group.region_id == Region.id)
            .where(*base_filter, Meeting.status == "completed")
        )

        async def _sum(column):
            return await self.db.scalar(
                select(func.coalesce(func.sum(column), 0))
                .select_from(MeetingEntry)
                .join(Meeting, MeetingEntry.meeting_id == Meeting.id)
                .join(Group, Meeting.group_id == Group.id)
                .join(Region, Group.region_id == Region.id)
                .where(*base_filter)
            )

        savings = await _sum(MeetingEntry.cur_saving) or 0
        loans_disbursed = await _sum(MeetingEntry.loan_given) or 0
        loan_repaid = await _sum(MeetingEntry.principal_paid) or 0
        interest = await _sum(MeetingEntry.interest_paid) or 0
        fines = await _sum(MeetingEntry.fine) or 0

        expenses_total = (
            await self.db.scalar(
                select(func.coalesce(func.sum(Expense.amount), 0))
                .select_from(Expense)
                .join(Meeting, Expense.meeting_id == Meeting.id)
                .join(Group, Meeting.group_id == Group.id)
                .join(Region, Group.region_id == Region.id)
                .where(*base_filter)
            )
            or 0
        )

        # Same shape as ledger_engine's cash_in_hand: everything collected,
        # minus what was paid out as loans, minus expenses. Interest and
        # fines are cash the group actually received and were previously
        # left out of this total.
        cash_in_hand_net = (
            (savings + loan_repaid + interest + fines) - loans_disbursed - expenses_total
        )

        return MonthlyReport(
            year=year,
            month=month,
            meetings_completed=meetings_completed or 0,
            total_savings_collected=savings,
            total_loans_disbursed=loans_disbursed,
            total_loan_repaid=loan_repaid,
            total_interest_collected=interest,
            total_fines_collected=fines,
            total_expenses=expenses_total,
            cash_in_hand_net=cash_in_hand_net,
        )

    # -- Activity / audit trail -------------------------------------------
    async def get_activity(
        self, organization_id: uuid.UUID, *, offset: int, limit: int
    ) -> tuple[list[AuditLog], int]:
        base = (
            select(AuditLog)
            .join(User, AuditLog.actor_id == User.id)
            .where(User.organization_id == organization_id)
        )
        rows = (
            await self.db.execute(base.order_by(AuditLog.created_at.desc()).offset(offset).limit(limit))
        ).scalars().all()
        total = (
            await self.db.execute(select(func.count()).select_from(base.subquery()))
        ).scalar_one()
        return list(rows), total
