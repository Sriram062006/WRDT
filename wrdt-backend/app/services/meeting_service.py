"""
Meeting Engine service — orchestrates the full meeting workflow:

    Start Meeting -> Edit / Auto-Save Draft -> Complete Meeting -> Permanent Lock

...plus the Savings/Loan/Carry-Forward rules that live inside a meeting's
ledger rows, and the Cash-in-Hand/expense totals, all delegated to the pure
`ledger_engine` module for calculation. This service is the ONLY place that
mutates `meeting_entries`/`expenses`/`meetings` — repositories only expose
raw queries, `ledger_engine` only computes, this file enforces the rules
and owns the transaction.

Permanent lock: enforced twice, deliberately redundant —
  1. HERE (service layer): every mutating method checks `meeting.locked`
     first and raises MeetingLockedError (-> clean 409) before touching
     the DB.
  2. At the DATABASE level via BEFORE triggers on meeting_entries/expenses
     (migrations/versions/0003_partial_indexes_and_triggers.py) — this is
     the actual guarantee; the service-layer check exists purely for a
     better error message, not as the source of truth.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

from app.core.constants import DEFAULT_CURRENT_SAVING, DEFAULT_REMARKS, MEETING_INTERVAL
from app.core.exceptions import MeetingLockedError, NotFoundError
from app.models.expense import Expense
from app.models.meeting import Meeting
from app.models.meeting_entry import MeetingEntry
from app.repositories.meeting_repo import ExpenseRepository, MeetingEntryRepository, MeetingRepository
from app.repositories.member_repo import MemberRepository
from app.schemas.expense import ExpenseCreate, ExpenseUpdate
from app.schemas.meeting import MeetingDetail, MeetingListItem
from app.schemas.meeting_entry import BulkEntryUpdate, MeetingEntryDraftUpdate
from app.services import ledger_engine
from app.services.audit_service import AuditService
from app.services.base import BaseService


class MeetingService(BaseService):
    def __init__(self, db):
        super().__init__(db)
        self.meetings = MeetingRepository(db)
        self.entries = MeetingEntryRepository(db)
        self.expenses = ExpenseRepository(db)
        self.members = MemberRepository(db)
        self.audit = AuditService(db)

    # ── Reads ────────────────────────────────────────────────────────
    async def get_or_404(self, meeting_id: uuid.UUID) -> Meeting:
        meeting = await self.meetings.get(meeting_id)
        if not meeting:
            raise NotFoundError("Meeting not found.")
        return meeting

    async def list_meetings(self, group_id: uuid.UUID, *, offset: int, limit: int) -> tuple[list[Meeting], int]:
        meetings = await self.meetings.list_by_group(group_id, offset=offset, limit=limit)
        total = await self.meetings.count_by_group(group_id)
        return meetings, total

    async def list_meetings_with_totals(
        self, group_id: uuid.UUID, *, offset: int, limit: int
    ) -> tuple[list[MeetingListItem], int]:
        rows = await self.meetings.list_by_group_with_totals(group_id, offset=offset, limit=limit)
        total = await self.meetings.count_by_group(group_id)
        items = [
            MeetingListItem(
                id=r["id"],
                group_id=r["group_id"],
                meeting_no=r["meeting_no"],
                meeting_date=r["meeting_date"],
                status=r["status"],
                locked=r["locked"],
                supervisor_id=r["supervisor_id"],
                members_present=r["members_present"],
                members_total=r["members_total"],
                total_saving=r["total_saving"],
                total_loan=r["total_loan"],
                total_expense=r["total_expense"],
                # Cash in Hand must match ledger_engine exactly:
                # cash collected - expenses - loans given out.
                cash_in_hand=r["total_cash_coll"] - r["total_expense"] - r["total_loan"],
            )
            for r in rows
        ]
        return items, total

    async def get_meeting_detail(self, meeting_id: uuid.UUID) -> MeetingDetail:
        meeting = await self.get_or_404(meeting_id)
        entries = await self.entries.list_by_meeting(meeting_id)
        expenses = await self.expenses.list_by_meeting(meeting_id)
        totals = ledger_engine.compute_totals(entries, expenses)
        return MeetingDetail(
            id=meeting.id,
            created_at=meeting.created_at,
            updated_at=meeting.updated_at,
            group_id=meeting.group_id,
            meeting_no=meeting.meeting_no,
            meeting_date=meeting.meeting_date,
            supervisor_id=meeting.supervisor_id,
            status=meeting.status,
            locked=meeting.locked,
            completed_at=meeting.completed_at,
            entries=[_entry_to_schema(e) for e in entries],
            expenses=[_expense_to_schema(x) for x in expenses],
            totals=totals,
        )

    # ── Start Meeting ────────────────────────────────────────────────
    async def start_meeting(
        self, group_id: uuid.UUID, actor_id: uuid.UUID | None, supervisor_id: uuid.UUID | None
    ) -> Meeting:
        """
        Idempotent: if the group already has an open (in_progress) meeting,
        that meeting is returned as-is rather than starting a new one —
        mirrors the frontend's startNewMeetingForGroup() early-return
        ("finish this week's page before starting next week's"). The
        one-open-meeting-per-group rule is additionally guaranteed at the
        DB level by a partial unique index, so this can never be violated
        even under a race condition.
        """
        existing_open = await self.meetings.get_open_meeting_for_group(group_id)
        if existing_open:
            return existing_open

        last_meeting = await self.meetings.get_last_meeting_for_group(group_id)

        if last_meeting is None:
            meeting_no = 1
            meeting_date = date.today()
        else:
            meeting_no = last_meeting.meeting_no + 1
            meeting_date = last_meeting.meeting_date + MEETING_INTERVAL

        meeting = Meeting(
            group_id=group_id,
            meeting_no=meeting_no,
            meeting_date=meeting_date,
            supervisor_id=supervisor_id,
            status="in_progress",
            locked=False,
        )
        self.meetings.add(meeting)
        await self.meetings.flush()

        # Materialize one ledger row per active member, carrying forward
        # from the previous meeting (or from the member's seed_* fields if
        # this is meeting #1) — see _build_carry_forward_entry below.
        active_members = [m for m in await self.members.list_by_group(group_id, offset=0, limit=100_000)]
        prior_entries_by_member: dict[uuid.UUID, MeetingEntry] = {}
        if last_meeting is not None:
            prior_entries = await self.entries.list_by_meeting(last_meeting.id)
            prior_entries_by_member = {e.member_id: e for e in prior_entries}

        for member in active_members:
            prior_entry = prior_entries_by_member.get(member.id)
            entry = _build_carry_forward_entry(meeting.id, member, prior_entry)
            self.entries.add(entry)

        await self.audit.record(
            actor_id=actor_id, action="meeting.start", entity_type="meeting",
            entity_id=meeting.id,
            after={"group_id": str(group_id), "meeting_no": meeting_no, "meeting_date": str(meeting_date)},
        )
        await self.meetings.commit()
        return meeting

    # ── Save Draft / Auto Save ──────────────────────────────────────
    async def save_entry_draft(
        self,
        meeting_id: uuid.UUID,
        member_id: uuid.UUID,
        payload: MeetingEntryDraftUpdate,
        actor_id: uuid.UUID | None,
    ) -> MeetingEntry:
        meeting = await self.get_or_404(meeting_id)
        self._ensure_not_locked(meeting)

        entry = await self.entries.get_by_meeting_and_member(meeting_id, member_id)
        if not entry:
            raise NotFoundError("This member does not have a ledger row in this meeting.")

        self._apply_draft_fields(entry, payload)

        await self.entries.flush()
        await self.audit.record(
            actor_id=actor_id, action="meeting_entry.draft_update", entity_type="meeting_entry",
            entity_id=entry.id, after=payload.model_dump(exclude_unset=True, mode="json"),
        )
        return await self.entries.commit_refresh(entry)

    async def save_entries_bulk(
        self, meeting_id: uuid.UUID, payload: BulkEntryUpdate, actor_id: uuid.UUID | None
    ) -> None:
        """Apply many row edits atomically. Either the whole sheet saves or
        none of it does -- a half-written register is worse than an
        unsaved one, because the supervisor cannot tell which rows made
        it."""
        meeting = await self.get_or_404(meeting_id)
        self._ensure_not_locked(meeting)

        existing = {e.member_id: e for e in await self.entries.list_by_meeting(meeting_id)}
        touched: list[uuid.UUID] = []
        for item in payload.entries:
            entry = existing.get(item.member_id)
            if entry is None:
                raise NotFoundError(
                    f"Member {item.member_id} does not have a ledger row in this meeting."
                )
            self._apply_draft_fields(entry, item)
            touched.append(item.member_id)

        await self.entries.flush()
        await self.audit.record(
            actor_id=actor_id, action="meeting_entry.bulk_update", entity_type="meeting",
            entity_id=meeting_id, after={"member_ids": [str(m) for m in touched]},
        )
        await self.meetings.commit()

    @staticmethod
    def _apply_draft_fields(entry: MeetingEntry, payload) -> None:
        loan_fields_touched = False
        if payload.present is not None:
            entry.present = payload.present
        if payload.cur_saving is not None:
            entry.cur_saving = payload.cur_saving
        if payload.loan_given is not None:
            entry.loan_given = payload.loan_given
            loan_fields_touched = True
        if payload.principal_paid is not None:
            entry.principal_paid = payload.principal_paid
            loan_fields_touched = True
        if payload.interest_paid is not None:
            entry.interest_paid = payload.interest_paid
        if payload.fine is not None:
            entry.fine = payload.fine
        if payload.remarks is not None:
            entry.remarks = payload.remarks

        if loan_fields_touched:
            # Mirrors the frontend's guard exactly:
            # if ((key === "loan" || key === "install") && !x.loanRemainingManual)
            ledger_engine.recalc_loan_remaining_if_auto(entry)

    async def add_expense(
        self, meeting_id: uuid.UUID, payload: ExpenseCreate, actor_id: uuid.UUID | None
    ) -> Expense:
        meeting = await self.get_or_404(meeting_id)
        self._ensure_not_locked(meeting)

        expense = Expense(meeting_id=meeting_id, expense_type=payload.expense_type, amount=payload.amount)
        self.expenses.add(expense)
        await self.expenses.flush()
        await self.audit.record(
            actor_id=actor_id, action="expense.create", entity_type="expense",
            entity_id=expense.id, after={"expense_type": expense.expense_type, "amount": str(expense.amount)},
        )
        return await self.expenses.commit_refresh(expense)

    async def update_expense(
        self, meeting_id: uuid.UUID, expense_id: uuid.UUID, payload: ExpenseUpdate, actor_id: uuid.UUID | None
    ) -> Expense:
        meeting = await self.get_or_404(meeting_id)
        self._ensure_not_locked(meeting)

        expense = await self.expenses.get_by_id_and_meeting(expense_id, meeting_id)
        if not expense:
            raise NotFoundError("Expense not found on this meeting.")

        before = {"expense_type": expense.expense_type, "amount": str(expense.amount)}
        if payload.expense_type is not None:
            expense.expense_type = payload.expense_type
        if payload.amount is not None:
            expense.amount = payload.amount

        await self.expenses.flush()
        await self.audit.record(
            actor_id=actor_id, action="expense.update", entity_type="expense",
            entity_id=expense.id, before=before,
            after={"expense_type": expense.expense_type, "amount": str(expense.amount)},
        )
        return await self.expenses.commit_refresh(expense)

    async def delete_expense(
        self, meeting_id: uuid.UUID, expense_id: uuid.UUID, actor_id: uuid.UUID | None
    ) -> None:
        meeting = await self.get_or_404(meeting_id)
        self._ensure_not_locked(meeting)

        expense = await self.expenses.get_by_id_and_meeting(expense_id, meeting_id)
        if not expense:
            raise NotFoundError("Expense not found on this meeting.")

        await self.expenses.delete(expense)
        await self.audit.record(
            actor_id=actor_id, action="expense.delete", entity_type="expense",
            entity_id=expense.id, before={"expense_type": expense.expense_type, "amount": str(expense.amount)},
        )
        await self.expenses.commit()

    # ── Loan Workflow: manual override / reset ──────────────────────
    async def override_loan_remaining(
        self, meeting_id: uuid.UUID, member_id: uuid.UUID, value, actor_id: uuid.UUID | None
    ) -> MeetingEntry:
        meeting = await self.get_or_404(meeting_id)
        self._ensure_not_locked(meeting)

        entry = await self.entries.get_by_meeting_and_member(meeting_id, member_id)
        if not entry:
            raise NotFoundError("This member does not have a ledger row in this meeting.")

        before = {"loan_remaining": str(entry.loan_remaining), "manual": entry.loan_remaining_manual}
        entry.loan_remaining = value
        entry.loan_remaining_manual = True

        await self.entries.flush()
        await self.audit.record(
            actor_id=actor_id, action="ledger_entry.loan_override", entity_type="meeting_entry",
            entity_id=entry.id, before=before,
            after={"loan_remaining": str(entry.loan_remaining), "manual": True},
        )
        return await self.entries.commit_refresh(entry)

    async def reset_loan_override(
        self, meeting_id: uuid.UUID, member_id: uuid.UUID, actor_id: uuid.UUID | None
    ) -> MeetingEntry:
        meeting = await self.get_or_404(meeting_id)
        self._ensure_not_locked(meeting)

        entry = await self.entries.get_by_meeting_and_member(meeting_id, member_id)
        if not entry:
            raise NotFoundError("This member does not have a ledger row in this meeting.")

        before = {"loan_remaining": str(entry.loan_remaining), "manual": entry.loan_remaining_manual}
        entry.loan_remaining_manual = False
        ledger_engine.recalc_loan_remaining_if_auto(entry)

        await self.entries.flush()
        await self.audit.record(
            actor_id=actor_id, action="ledger_entry.loan_reset", entity_type="meeting_entry",
            entity_id=entry.id, before=before,
            after={"loan_remaining": str(entry.loan_remaining), "manual": False},
        )
        return await self.entries.commit_refresh(entry)

    # ── Complete Meeting / Permanent Lock ───────────────────────────
    async def complete_meeting(self, meeting_id: uuid.UUID, actor_id: uuid.UUID | None) -> Meeting:
        meeting = await self.get_or_404(meeting_id)
        if meeting.status == "completed":
            # Idempotent, matches the frontend's own guard: calling complete
            # again on an already-completed meeting is a no-op, not an error.
            return meeting

        entries = await self.entries.list_by_meeting(meeting_id)
        expenses = await self.expenses.list_by_meeting(meeting_id)
        totals = ledger_engine.compute_totals(entries, expenses)

        meeting.status = "completed"
        meeting.locked = True
        meeting.completed_at = datetime.now(timezone.utc)

        await self.meetings.flush()
        await self.audit.record(
            actor_id=actor_id, action="meeting.complete", entity_type="meeting",
            entity_id=meeting.id,
            after={
                "cash_in_hand": str(totals.cash_in_hand),
                "tot_total_saving": str(totals.tot_total_saving),
                "loan_remaining": str(totals.loan_remaining),
            },
        )
        await self.meetings.commit()
        return meeting

    # ── Member <-> open-meeting sync (called by MemberService) ──────
    async def sync_new_member_into_open_meeting(self, group_id: uuid.UUID, member) -> None:
        """
        Mirrors the frontend's syncNewMembersIntoOpenLedger(): if this
        group currently has an open meeting, the new member gets a ledger
        row immediately, seeded from their seed_* fields exactly like a
        meeting #1 row (a brand-new member has no prior meeting to carry
        forward from, regardless of what meeting number the group is on).
        Groups with no open meeting are untouched — the member appears
        automatically the next time a meeting is started for that group.
        """
        open_meeting = await self.meetings.get_open_meeting_for_group(group_id)
        if not open_meeting:
            return
        entry = _build_carry_forward_entry(open_meeting.id, member, prior_entry=None)
        self.entries.add(entry)
        await self.entries.commit()

    async def remove_member_from_open_meeting(self, group_id: uuid.UUID, member_id: uuid.UUID) -> None:
        """Mirrors removeMemberFromOpenLedger(): only ever touches the
        currently open meeting's row for this member; completed meetings
        are historical and are never modified (also enforced by the DB
        lock trigger regardless)."""
        open_meeting = await self.meetings.get_open_meeting_for_group(group_id)
        if not open_meeting:
            return
        entry = await self.entries.get_by_meeting_and_member(open_meeting.id, member_id)
        if entry:
            await self.entries.delete(entry)
            await self.entries.commit()

    # ── internal ─────────────────────────────────────────────────────
    def _ensure_not_locked(self, meeting: Meeting) -> None:
        if meeting.locked or meeting.status == "completed":
            raise MeetingLockedError(
                "This meeting has been completed and is permanently locked. "
                "No further changes are possible."
            )


def _build_carry_forward_entry(meeting_id: uuid.UUID, member, prior_entry: MeetingEntry | None) -> MeetingEntry:
    """
    The carry-forward computation, executed once at meeting-start time (or
    at member-creation time if joining an already-open meeting) — never
    computed lazily at read-time. Mirrors the frontend's getLedger():

        next.prev_saving            = prior.prev_saving + prior.cur_saving
        next.loan_remaining_opening = prior.loan_remaining   (auto OR manual, whichever froze)
        next.paid_till_date_opening = prior.paid_till_date_opening + prior.principal_paid

    For a member's very first row (no prior_entry — either meeting #1 for
    the whole group, or a brand-new member joining an in-progress meeting),
    opening values come from the member's seed_* fields instead.

    The previous entry is only ever READ here, never written — completed
    meetings remain untouched.
    """
    if prior_entry is not None:
        opening_prev_saving = prior_entry.prev_saving + prior_entry.cur_saving
        opening_loan_remaining = prior_entry.loan_remaining
        opening_paid_till_date = prior_entry.paid_till_date_opening + prior_entry.principal_paid
        fine_default = 0
    else:
        opening_prev_saving = member.seed_prev_saving
        opening_loan_remaining = member.seed_loan
        opening_paid_till_date = 0
        fine_default = member.seed_fine

    return MeetingEntry(
        meeting_id=meeting_id,
        member_id=member.id,
        present=True,
        prev_saving=opening_prev_saving,
        cur_saving=DEFAULT_CURRENT_SAVING,
        loan_given=0,
        # seed_install is historical context about the member, not a
        # repayment made at THIS meeting. Pre-filling it here charged every
        # brand-new member an unmade installment on their first row (and
        # the frontend prototype never did this either).
        principal_paid=0,
        interest_paid=0,
        paid_till_date_opening=opening_paid_till_date,
        loan_remaining_opening=opening_loan_remaining,
        loan_remaining=opening_loan_remaining,
        loan_remaining_manual=False,
        fine=fine_default,
        remarks=DEFAULT_REMARKS,
    )


def _entry_to_schema(entry: MeetingEntry):
    from app.schemas.meeting_entry import MeetingEntryRead

    return MeetingEntryRead.model_validate(entry)


def _expense_to_schema(expense: Expense):
    from app.schemas.expense import ExpenseRead

    return ExpenseRead.model_validate(expense)
