"""
Excel Export service — renders a completed or in-progress meeting's ledger
to an .xlsx workbook that mirrors the on-screen Meeting Register exactly
(same columns, same bottom totals row), reusing `ledger_engine.compute_totals`
so the exported numbers can never drift from what the API/UI shows.
"""
from __future__ import annotations

import io
import uuid

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter

from app.core.exceptions import NotFoundError
from app.repositories.meeting_repo import ExpenseRepository, MeetingEntryRepository, MeetingRepository
from app.repositories.member_repo import MemberRepository
from app.services import ledger_engine
from app.services.base import BaseService

_HEADERS = [
    "Member", "Prev Saving", "Cur Saving", "Total Saving",
    "Loan Given", "Principal Paid", "Interest", "Paid Till Date", "Remaining Loan",
    "Fine", "Cash Paid", "Present", "Remarks",
]


class ExcelExportService(BaseService):
    def __init__(self, db):
        super().__init__(db)
        self.meetings = MeetingRepository(db)
        self.entries = MeetingEntryRepository(db)
        self.expenses = ExpenseRepository(db)
        self.members = MemberRepository(db)

    async def export_meeting(self, meeting_id: uuid.UUID) -> tuple[bytes, str]:
        meeting = await self.meetings.get(meeting_id)
        if not meeting:
            raise NotFoundError("Meeting not found.")

        entries = await self.entries.list_by_meeting(meeting_id)
        expenses = await self.expenses.list_by_meeting(meeting_id)
        totals = ledger_engine.compute_totals(entries, expenses)

        member_ids = [e.member_id for e in entries]
        members_by_id: dict[uuid.UUID, str] = {}
        for mid in member_ids:
            if mid not in members_by_id:
                m = await self.members.get(mid)
                members_by_id[mid] = m.name if m else str(mid)

        wb = Workbook()
        ws = wb.active
        ws.title = f"Meeting {meeting.meeting_no}"

        ws.append([f"Meeting #{meeting.meeting_no}", "", f"Date: {meeting.meeting_date.isoformat()}"])
        ws.append([f"Status: {meeting.status}"])
        ws.append([])

        header_row_idx = ws.max_row + 1
        ws.append(_HEADERS)
        for col in range(1, len(_HEADERS) + 1):
            cell = ws.cell(row=header_row_idx, column=col)
            cell.font = Font(bold=True, color="FFFFFF")
            cell.fill = PatternFill("solid", fgColor="16A34A")

        for e in sorted(entries, key=lambda x: members_by_id.get(x.member_id, "")):
            ws.append([
                members_by_id.get(e.member_id, str(e.member_id)),
                float(e.prev_saving), float(e.cur_saving), float(e.prev_saving) + float(e.cur_saving),
                float(e.loan_given), float(e.principal_paid), float(e.interest_paid),
                float(e.paid_till_date_opening) + float(e.principal_paid), float(e.loan_remaining),
                float(e.fine), float(ledger_engine.row_cash_paid(e)),
                "Yes" if e.present else "No", e.remarks,
            ])

        totals_row_idx = ws.max_row + 1
        ws.append([
            "TOTAL", float(totals.tot_prev_saving), float(totals.tot_savings), float(totals.tot_total_saving),
            float(totals.tot_loan), float(totals.tot_install), float(totals.tot_interest),
            float(totals.tot_paid_till_date), float(totals.loan_remaining), float(totals.tot_fine),
            float(totals.tot_cash_coll), "", "",
        ])
        for col in range(1, len(_HEADERS) + 1):
            ws.cell(row=totals_row_idx, column=col).font = Font(bold=True)

        ws.append([])
        ws.append(["Total Expense", float(totals.tot_expense)])
        ws.append(["Cash in Hand", float(totals.cash_in_hand)])
        ws.append(["Present", totals.present, "Absent", totals.absent])

        if expenses:
            ws.append([])
            ws.append(["Expense Type", "Amount"])
            for x in expenses:
                ws.append([x.expense_type, float(x.amount)])

        for col in range(1, len(_HEADERS) + 1):
            ws.column_dimensions[get_column_letter(col)].width = 16

        buf = io.BytesIO()
        wb.save(buf)
        buf.seek(0)

        filename = f"meeting_{meeting.meeting_no}_{meeting.meeting_date.isoformat()}.xlsx"
        return buf.read(), filename
