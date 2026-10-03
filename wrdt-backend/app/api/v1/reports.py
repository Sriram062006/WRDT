"""
Reports & Dashboard routes -- read-only aggregates available to Owner
(unrestricted within their organization) and Supervisor ("View Reports"
is in the Supervisor permission list, scoped to assigned groups).

Every scoped report resolves its subject through `app.services.access`,
so a Supervisor cannot pull numbers for a group they are not assigned to
and no one can pull numbers from another organization.
"""
from __future__ import annotations

import uuid
from datetime import date

from fastapi import APIRouter, Depends, Query

from app.api.deps import CurrentUserDep, DbSession, PageParamsDep, require_role
from app.schemas.audit_log import AuditLogRead
from app.schemas.base import Page
from app.schemas.reports import (
    DashboardStats,
    ExpenseReport,
    GroupReport,
    LoanLedgerReport,
    MemberLedgerReport,
    MonthlyReport,
    RegionReport,
)
from app.services import access
from app.services.report_service import ReportService

router = APIRouter(dependencies=[Depends(require_role("owner", "supervisor"))])


@router.get("/dashboard", response_model=DashboardStats, summary="Dashboard statistics")
async def dashboard_stats(db: DbSession, current_user: CurrentUserDep):
    service = ReportService(db)
    scope = None if current_user.role_name == "owner" else await access.visible_group_ids(
        db, current_user
    )
    return await service.get_dashboard_stats(current_user.organization_id, group_scope=scope)


@router.get(
    "/collections",
    response_model=list[dict],
    summary="Collection totals per meeting date (dashboard chart)",
)
async def collection_series(
    db: DbSession,
    current_user: CurrentUserDep,
    days: int = Query(30, ge=7, le=365),
):
    """Backs the dashboard's collection chart. Previously the chart drew a
    hard-coded array of seven invented figures."""
    scope = None if current_user.role_name == "owner" else await access.visible_group_ids(
        db, current_user
    )
    return await ReportService(db).get_collection_series(
        current_user.organization_id, days=days, group_scope=scope
    )


@router.get(
    "/members/{member_id}/ledger", response_model=MemberLedgerReport, summary="Member ledger report"
)
async def member_ledger(member_id: uuid.UUID, db: DbSession, current_user: CurrentUserDep):
    await access.resolve_member(db, current_user, member_id)
    return await ReportService(db).get_member_ledger(member_id)


@router.get("/loans", response_model=LoanLedgerReport, summary="Loan ledger (outstanding loans)")
async def loan_ledger(
    db: DbSession,
    current_user: CurrentUserDep,
    region_id: uuid.UUID | None = Query(None),
    group_id: uuid.UUID | None = Query(None),
):
    """
    A Supervisor without a group filter used to receive a hard 422 telling
    them to pick a group -- which made the Loans screen unusable for the
    role that most needs it. They now see the union of their assigned
    groups, which is exactly the data they are already authorised for.
    """
    if group_id is not None:
        await access.assert_group_access(db, current_user, group_id)
    if region_id is not None:
        await access.resolve_region(db, current_user, region_id)

    scope = None if current_user.role_name == "owner" else await access.visible_group_ids(
        db, current_user
    )
    return await ReportService(db).get_loan_ledger(
        current_user.organization_id, region_id=region_id, group_id=group_id, group_scope=scope
    )


@router.get("/expenses", response_model=ExpenseReport, summary="Expense report")
async def expense_report(
    db: DbSession,
    current_user: CurrentUserDep,
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    group_id: uuid.UUID | None = Query(None),
):
    if group_id is not None:
        await access.assert_group_access(db, current_user, group_id)
    scope = None if current_user.role_name == "owner" else await access.visible_group_ids(
        db, current_user
    )
    return await ReportService(db).get_expense_report(
        current_user.organization_id,
        date_from=date_from,
        date_to=date_to,
        group_id=group_id,
        group_scope=scope,
    )


@router.get("/groups/{group_id}", response_model=GroupReport, summary="Group report")
async def group_report(
    group_id: uuid.UUID,
    db: DbSession,
    current_user: CurrentUserDep,
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
):
    await access.assert_group_access(db, current_user, group_id)
    return await ReportService(db).get_group_report(group_id, date_from=date_from, date_to=date_to)


@router.get(
    "/regions/{region_id}",
    response_model=RegionReport,
    summary="Region report",
    dependencies=[Depends(require_role("owner"))],
)
async def region_report(
    region_id: uuid.UUID,
    db: DbSession,
    current_user: CurrentUserDep,
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
):
    await access.resolve_region(db, current_user, region_id)
    return await ReportService(db).get_region_report(
        region_id, date_from=date_from, date_to=date_to
    )


@router.get(
    "/monthly",
    response_model=MonthlyReport,
    summary="Monthly report",
    dependencies=[Depends(require_role("owner"))],
)
async def monthly_report(
    db: DbSession,
    current_user: CurrentUserDep,
    year: int = Query(..., ge=2000, le=2100),
    month: int = Query(..., ge=1, le=12),
):
    return await ReportService(db).get_monthly_report(current_user.organization_id, year, month)


@router.get(
    "/activity",
    response_model=Page[AuditLogRead],
    summary="Recent activity (audit trail)",
    dependencies=[Depends(require_role("owner"))],
)
async def activity(db: DbSession, page_params: PageParamsDep, current_user: CurrentUserDep):
    """Backs the Activity screen. The UI previously showed a hard-coded
    unread badge of "3" with nothing behind it; this is the real audit
    trail, scoped to actors inside the caller's organization."""
    items, total = await ReportService(db).get_activity(
        current_user.organization_id, offset=page_params.offset, limit=page_params.page_size
    )
    return Page(
        items=[AuditLogRead.model_validate(a) for a in items],
        total=total,
        page=page_params.page,
        page_size=page_params.page_size,
    )
