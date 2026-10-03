"""
Meeting Engine routes.

Both Owner and Supervisor may run the meeting workflow (Start/Draft/
Complete are explicitly in the Supervisor permission list). Access is
scoped per object, not by role alone: every route resolves the meeting
through `access.resolve_meeting`, which checks the caller's organization
AND (for Supervisors) their group assignments. That is what makes these
routes IDOR-safe even though the URL carries only a meeting_id.

Two routers:
  - `nested_router` -> /groups/{group_id}/meetings (list, start)
  - `router`        -> /meetings/{meeting_id}      (everything else)
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, status
from fastapi.responses import Response

from app.api.deps import CurrentUserDep, DbSession, PageParamsDep, require_role
from app.schemas.base import Page
from app.schemas.expense import ExpenseCreate, ExpenseRead, ExpenseUpdate
from app.schemas.meeting import MeetingDetail, MeetingListItem
from app.schemas.meeting_entry import (
    BulkEntryUpdate,
    LoanOverrideRequest,
    MeetingEntryDraftUpdate,
    MeetingEntryRead,
)
from app.services import access
from app.services.excel_export_service import ExcelExportService
from app.services.meeting_service import MeetingService

nested_router = APIRouter(dependencies=[Depends(require_role("owner", "supervisor"))])
router = APIRouter(dependencies=[Depends(require_role("owner", "supervisor"))])


# -- Group-scoped: list & start ------------------------------------------
@nested_router.get("", response_model=Page[MeetingListItem], summary="List meetings for a group")
async def list_meetings(
    group_id: uuid.UUID, db: DbSession, page_params: PageParamsDep, current_user: CurrentUserDep
):
    await access.assert_group_access(db, current_user, group_id)
    service = MeetingService(db)
    items, total = await service.list_meetings_with_totals(
        group_id, offset=page_params.offset, limit=page_params.page_size
    )
    return Page(items=items, total=total, page=page_params.page, page_size=page_params.page_size)


@nested_router.post(
    "/start",
    response_model=MeetingDetail,
    status_code=status.HTTP_201_CREATED,
    summary="Start (or resume) a meeting",
)
async def start_meeting(group_id: uuid.UUID, db: DbSession, current_user: CurrentUserDep):
    await access.assert_group_access(db, current_user, group_id)
    service = MeetingService(db)
    # Record whoever actually opened the register as its supervisor,
    # whatever their role. The previous version stored NULL for an Owner,
    # leaving the register's "Supervisor" field blank on the printout.
    meeting = await service.start_meeting(group_id, current_user.id, current_user.id)
    return await service.get_meeting_detail(meeting.id)


# -- Meeting-scoped -------------------------------------------------------
@router.get(
    "/{meeting_id}", response_model=MeetingDetail, summary="Get meeting register (entries + totals)"
)
async def get_meeting(meeting_id: uuid.UUID, db: DbSession, current_user: CurrentUserDep):
    await access.resolve_meeting(db, current_user, meeting_id)
    return await MeetingService(db).get_meeting_detail(meeting_id)


@router.put(
    "/{meeting_id}/entries/{member_id}",
    response_model=MeetingEntryRead,
    summary="Save draft: update one member's ledger row",
)
async def save_entry_draft(
    meeting_id: uuid.UUID,
    member_id: uuid.UUID,
    payload: MeetingEntryDraftUpdate,
    db: DbSession,
    current_user: CurrentUserDep,
):
    await access.resolve_meeting(db, current_user, meeting_id)
    entry = await MeetingService(db).save_entry_draft(meeting_id, member_id, payload, current_user.id)
    return MeetingEntryRead.model_validate(entry)


@router.put(
    "/{meeting_id}/entries",
    response_model=MeetingDetail,
    summary="Save draft: update many ledger rows in one transaction",
)
async def save_entries_bulk(
    meeting_id: uuid.UUID,
    payload: BulkEntryUpdate,
    db: DbSession,
    current_user: CurrentUserDep,
):
    """
    The register is edited as a whole sheet -- "apply the same saving to
    all 17 members" is one user action. Sending 17 individual PUTs made
    that non-atomic (a failure halfway left the register half-saved) and
    slow over a rural mobile connection. This applies them in a single
    transaction and returns the recomputed totals.
    """
    await access.resolve_meeting(db, current_user, meeting_id)
    service = MeetingService(db)
    await service.save_entries_bulk(meeting_id, payload, current_user.id)
    return await service.get_meeting_detail(meeting_id)


@router.patch(
    "/{meeting_id}/entries/{member_id}/loan-override",
    response_model=MeetingEntryRead,
    summary="Manually override Remaining Loan",
)
async def override_loan(
    meeting_id: uuid.UUID,
    member_id: uuid.UUID,
    payload: LoanOverrideRequest,
    db: DbSession,
    current_user: CurrentUserDep,
):
    await access.resolve_meeting(db, current_user, meeting_id)
    entry = await MeetingService(db).override_loan_remaining(
        meeting_id, member_id, payload.loan_remaining, current_user.id
    )
    return MeetingEntryRead.model_validate(entry)


@router.delete(
    "/{meeting_id}/entries/{member_id}/loan-override",
    response_model=MeetingEntryRead,
    summary="Reset Remaining Loan back to auto-calculated",
)
async def reset_loan(
    meeting_id: uuid.UUID, member_id: uuid.UUID, db: DbSession, current_user: CurrentUserDep
):
    await access.resolve_meeting(db, current_user, meeting_id)
    entry = await MeetingService(db).reset_loan_override(meeting_id, member_id, current_user.id)
    return MeetingEntryRead.model_validate(entry)


@router.post(
    "/{meeting_id}/expenses",
    response_model=ExpenseRead,
    status_code=status.HTTP_201_CREATED,
    summary="Add an expense line item",
)
async def add_expense(
    meeting_id: uuid.UUID, payload: ExpenseCreate, db: DbSession, current_user: CurrentUserDep
):
    await access.resolve_meeting(db, current_user, meeting_id)
    expense = await MeetingService(db).add_expense(meeting_id, payload, current_user.id)
    return ExpenseRead.model_validate(expense)


@router.put(
    "/{meeting_id}/expenses/{expense_id}",
    response_model=ExpenseRead,
    summary="Update an expense line item",
)
async def update_expense(
    meeting_id: uuid.UUID,
    expense_id: uuid.UUID,
    payload: ExpenseUpdate,
    db: DbSession,
    current_user: CurrentUserDep,
):
    await access.resolve_meeting(db, current_user, meeting_id)
    expense = await MeetingService(db).update_expense(meeting_id, expense_id, payload, current_user.id)
    return ExpenseRead.model_validate(expense)


@router.delete(
    "/{meeting_id}/expenses/{expense_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an expense line item",
)
async def delete_expense(
    meeting_id: uuid.UUID, expense_id: uuid.UUID, db: DbSession, current_user: CurrentUserDep
):
    await access.resolve_meeting(db, current_user, meeting_id)
    await MeetingService(db).delete_expense(meeting_id, expense_id, current_user.id)


@router.post(
    "/{meeting_id}/complete",
    response_model=MeetingDetail,
    summary="Complete meeting (PERMANENT -- cannot be undone)",
)
async def complete_meeting(meeting_id: uuid.UUID, db: DbSession, current_user: CurrentUserDep):
    await access.resolve_meeting(db, current_user, meeting_id)
    service = MeetingService(db)
    await service.complete_meeting(meeting_id, current_user.id)
    return await service.get_meeting_detail(meeting_id)


@router.get(
    "/{meeting_id}/export.xlsx",
    summary="Export the meeting register to an Excel workbook",
    response_class=Response,
)
async def export_meeting_xlsx(meeting_id: uuid.UUID, db: DbSession, current_user: CurrentUserDep):
    # Read-only export; safe on both in-progress and completed meetings
    # (a supervisor may want to print/export a draft mid-meeting).
    await access.resolve_meeting(db, current_user, meeting_id)
    content, filename = await ExcelExportService(db).export_meeting(meeting_id)
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
