"""
Excel Import service — two-phase preview/commit, ported 1:1 from the
frontend's `processImportRows(rows, {commit})`:

  - Expected columns: Region, Group, Member, Previous Saving (matching the
    frontend's import template exactly — column layout is NOT changed).
  - Duplicate detection is case-insensitive and scoped correctly: Region
    globally unique per Organization, Group unique per Region, Member
    unique per Group (same rule the CRUD services already enforce).
  - `preview_import` is READ-ONLY — it classifies every row but writes
    nothing to regions/groups/members, only an ImportHistory row recording
    the batch (status='previewed') so it can be re-fetched/audited even
    before a commit.
  - `commit_import` re-runs the IDENTICAL classification function inside a
    single DB transaction, this time actually inserting rows — preview and
    commit can never disagree because they share one `_classify_rows()`
    call, exactly like the frontend's shared-function design.
  - New members are synced into their group's currently-open meeting
    immediately on commit (mirrors syncNewMembersIntoOpenLedger), via a
    local import of MeetingService to avoid a circular import.
"""
from __future__ import annotations

import io
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation

from openpyxl import Workbook, load_workbook

from app.core.exceptions import NotFoundError, ValidationAppError
from app.models.group import Group
from app.models.import_history import ImportHistory
from app.models.member import Member
from app.models.region import Region
from app.repositories.group_repo import GroupRepository
from app.repositories.import_repo import ImportHistoryRepository
from app.repositories.member_repo import MemberRepository
from app.repositories.region_repo import RegionRepository
from app.schemas.import_history import ImportPreviewResponse, ImportRowResult, ImportSummary
from app.services.base import BaseService

EXPECTED_HEADERS = ["region", "group", "member", "previous saving"]


@dataclass
class _ParsedRow:
    region: str
    group: str
    member: str
    prev_saving: Decimal | None
    row_number: int


@dataclass
class _ClassificationResult:
    rows: list[ImportRowResult] = field(default_factory=list)
    regions_created: int = 0
    groups_created: int = 0
    members_created: int = 0
    regions_skipped: int = 0
    groups_skipped: int = 0
    members_skipped: int = 0
    invalid_rows: int = 0


def _parse_workbook(file_bytes: bytes) -> list[_ParsedRow]:
    try:
        wb = load_workbook(io.BytesIO(file_bytes), read_only=True, data_only=True)
    except Exception as exc:  # noqa: BLE001 — surfaced as a clean validation error
        raise ValidationAppError(f"Could not read the uploaded file as an Excel workbook: {exc}")

    ws = wb.active
    rows_iter = ws.iter_rows(values_only=True)
    try:
        header = next(rows_iter)
    except StopIteration:
        raise ValidationAppError("The uploaded file is empty.")

    header_lower = [str(h).strip().lower() if h is not None else "" for h in header]

    def find(*aliases: str) -> int | None:
        """Real register exports are not header-consistent: the same
        column appears as 'Member', 'Member Name' or 'Name' depending on
        who produced the sheet, and the saving column is pluralised about
        half the time. Rejecting those files outright forced staff to
        hand-edit every spreadsheet before import, so accept the known
        spellings instead."""
        for alias in aliases:
            if alias in header_lower:
                return header_lower.index(alias)
        return None

    idx_region = find("region", "region name")
    idx_group = find("group", "group name", "shg", "sangam")
    idx_member = find("member name", "member", "name")
    missing = [
        label
        for label, idx in (("Region", idx_region), ("Group", idx_group), ("Member Name", idx_member))
        if idx is None
    ]
    if missing:
        raise ValidationAppError(
            f"The uploaded file is missing required column(s): {', '.join(missing)}. "
            "Expected: Region, Group, Member Name, Previous Savings (optional)."
        )
    idx_prev_saving = find(
        "previous savings", "previous saving", "prev saving", "opening savings", "opening saving"
    )

    parsed: list[_ParsedRow] = []
    for i, row in enumerate(rows_iter, start=2):  # row 1 is the header
        if row is None or all(c is None or str(c).strip() == "" for c in row):
            continue  # skip fully blank rows

        def cell(idx: int | None) -> str:
            if idx is None or idx >= len(row) or row[idx] is None:
                return ""
            return str(row[idx]).strip()

        prev_saving_raw = cell(idx_prev_saving) if idx_prev_saving is not None else ""
        prev_saving: Decimal | None
        try:
            # Excel hands back "12,500", "12500.0" or "\u20b912500" depending on how
            # the source sheet was formatted; strip the decoration rather
            # than failing the row.
            cleaned = prev_saving_raw.replace(",", "").replace("\u20b9", "").strip()
            prev_saving = Decimal(cleaned) if cleaned else Decimal("0")
            if prev_saving < 0:
                prev_saving = None
        except InvalidOperation:
            prev_saving = None  # marks the row invalid at classification time

        parsed.append(
            _ParsedRow(
                region=cell(idx_region),
                group=cell(idx_group),
                member=cell(idx_member),
                prev_saving=prev_saving,
                row_number=i,
            )
        )
    return parsed


class ExcelImportService(BaseService):
    @staticmethod
    def build_template() -> bytes:
        wb = Workbook()
        ws = wb.active
        ws.title = "Members"
        ws.append(["Region", "Group", "Member Name", "Previous Savings"])
        ws.append(["Jagadevi", "Lakshmi SHG", "R. Lakshmi", 4400])
        for i, width in enumerate((22, 24, 28, 18), start=1):
            ws.column_dimensions[chr(64 + i)].width = width
        buf = io.BytesIO()
        wb.save(buf)
        buf.seek(0)
        return buf.read()

    def __init__(self, db):
        super().__init__(db)
        self.imports = ImportHistoryRepository(db)
        self.regions = RegionRepository(db)
        self.groups = GroupRepository(db)
        self.members = MemberRepository(db)

    async def _classify_rows(
        self, organization_id: uuid.UUID, parsed_rows: list[_ParsedRow], *, commit: bool, actor_id: uuid.UUID | None
    ) -> _ClassificationResult:
        result = _ClassificationResult()

        # In-memory caches so a batch that mentions the same new Region/Group
        # multiple times only creates (or counts) it ONCE, even across rows
        # within one batch (mirrors the frontend's in-batch de-duplication).
        # A cached value of `_PENDING` means "confirmed new within this
        # batch, not yet a real persisted row" (relevant for preview mode,
        # where nothing is actually inserted) — deliberately NOT `None`,
        # so a second row referencing the same new group doesn't re-trigger
        # region_created/group_created counting.
        _PENDING = object()
        region_cache: dict[str, Region | object] = {}
        group_cache: dict[tuple[str, str], Group | object] = {}

        for row in parsed_rows:
            if not row.region or not row.group or not row.member or row.prev_saving is None:
                result.invalid_rows += 1
                result.rows.append(
                    ImportRowResult(
                        region=row.region, group=row.group, member=row.member,
                        prev_saving=None, status="Invalid",
                        detail=f"Row {row.row_number}: missing or invalid required field(s).",
                    )
                )
                continue

            # ── Region ──
            region_key = row.region.strip().lower()
            region_is_new = False
            if region_key in region_cache:
                region = region_cache[region_key]
            else:
                region = await self.regions.get_by_name_ci(organization_id, row.region)
                if region is None:
                    region_is_new = True
                    if commit:
                        region = Region(organization_id=organization_id, name=row.region.strip(),
                                         status="Active", created_by=actor_id)
                        self.regions.add(region)
                        await self.regions.flush()
                    else:
                        region = _PENDING
                    result.regions_created += 1
                region_cache[region_key] = region

            region_real = region if region is not _PENDING else None

            # ── Group ──
            group_key = (region_key, row.group.strip().lower())
            if group_key in group_cache:
                group = group_cache[group_key]
            else:
                group = None
                if region_real is not None:
                    group = await self.groups.get_by_name_ci(region_real.id, row.group)
                if group is None:
                    if commit and region_real is not None:
                        group = Group(region_id=region_real.id, name=row.group.strip(),
                                       formed_date=date.today(), status="Active", created_by=actor_id)
                        self.groups.add(group)
                        await self.groups.flush()
                    else:
                        group = _PENDING
                    result.groups_created += 1
                group_cache[group_key] = group

            group_real = group if group is not _PENDING else None

            # ── Member (duplicate check only meaningful against a real,
            # already-persisted group; a brand-new group can't have an
            # existing member by definition) ──
            member_exists = False
            if group_real is not None:
                existing_member = await self.members.get_by_name_ci(group_real.id, row.member)
                member_exists = existing_member is not None

            if member_exists:
                result.members_skipped += 1
                result.rows.append(
                    ImportRowResult(
                        region=row.region, group=row.group, member=row.member,
                        prev_saving=float(row.prev_saving), status="Skipped",
                        detail="A member with this name already exists in this group.",
                    )
                )
                continue

            if commit and group_real is not None:
                sequence = await self.members.count_existing_in_group(group_real.id) + 1
                from app.services.member_service import _generate_code

                member = Member(
                    group_id=group_real.id,
                    code=_generate_code(group_real.name, sequence),
                    name=row.member.strip(),
                    joined_date=date.today(),
                    status="Active",
                    seed_prev_saving=row.prev_saving,
                    seed_loan=Decimal("0"),
                    seed_install=Decimal("0"),
                    seed_fine=Decimal("0"),
                    created_by=actor_id,
                )
                self.members.add(member)
                await self.members.flush()
                result.members_created += 1

                # Sync into the group's open meeting, if any (mirrors
                # syncNewMembersIntoOpenLedger) — local import to avoid a
                # circular import at module load time.
                from app.services.meeting_service import MeetingService

                await MeetingService(self.db).sync_new_member_into_open_meeting(group_real.id, member)
            else:
                result.members_created += 1  # preview-only count

            result.rows.append(
                ImportRowResult(
                    region=row.region, group=row.group, member=row.member,
                    prev_saving=float(row.prev_saving), status="Imported",
                    detail="New member." if not region_is_new else "New region, group, and member.",
                )
            )

        return result

    async def preview_import(
        self, organization_id: uuid.UUID, file_bytes: bytes, file_name: str, actor_id: uuid.UUID | None
    ) -> ImportPreviewResponse:
        parsed_rows = _parse_workbook(file_bytes)
        result = await self._classify_rows(organization_id, parsed_rows, commit=False, actor_id=actor_id)

        # Preview never writes region/group/member rows (see _PENDING marker
        # in _classify_rows), but DOES persist the batch record itself
        # (status='previewed') so it's queryable and can be committed by
        # batch_id afterward without re-uploading the file.
        batch = ImportHistory(
            organization_id=organization_id,
            uploaded_by=actor_id,
            file_name=file_name,
            status="previewed",
            total_rows=len(parsed_rows),
            regions_created=result.regions_created,
            groups_created=result.groups_created,
            members_created=result.members_created,
            invalid_rows=result.invalid_rows,
            raw_payload={
                "rows": [r.model_dump(mode="json") for r in result.rows],
                # Store the parsed raw rows too, so commit() doesn't require
                # the file to be re-uploaded.
                "parsed_rows": [
                    {"region": r.region, "group": r.group, "member": r.member,
                     "prev_saving": str(r.prev_saving) if r.prev_saving is not None else None,
                     "row_number": r.row_number}
                    for r in parsed_rows
                ],
            },
        )
        self.imports.add(batch)
        await self.imports.flush()
        await self.imports.commit()

        summary = ImportSummary(
            total=len(parsed_rows),
            regions_created=result.regions_created,
            groups_created=result.groups_created,
            members_created=result.members_created,
            regions_skipped=0,
            groups_skipped=0,
            members_skipped=result.members_skipped,
            invalid_rows=result.invalid_rows,
        )
        return ImportPreviewResponse(batch_id=batch.id, summary=summary, rows=result.rows)

    async def commit_import(
        self, batch_id: uuid.UUID, organization_id: uuid.UUID, actor_id: uuid.UUID | None
    ) -> ImportPreviewResponse:
        batch = await self.imports.get(batch_id)
        # The batch carries the organization the rows will be written
        # into. Without this check an Owner could commit another tenant's
        # previewed batch, creating regions/groups/members inside it.
        if not batch or batch.organization_id != organization_id:
            raise NotFoundError("Import batch not found.")
        if batch.status == "committed":
            raise ValidationAppError("This import batch has already been committed.")
        if not batch.raw_payload or "parsed_rows" not in batch.raw_payload:
            raise ValidationAppError(
                "This import batch has no stored rows and must be re-uploaded."
            )

        parsed_rows = [
            _ParsedRow(
                region=r["region"], group=r["group"], member=r["member"],
                prev_saving=Decimal(r["prev_saving"]) if r["prev_saving"] is not None else None,
                row_number=r["row_number"],
            )
            for r in batch.raw_payload["parsed_rows"]
        ]

        result = await self._classify_rows(batch.organization_id, parsed_rows, commit=True, actor_id=actor_id)

        batch.status = "committed"
        batch.regions_created = result.regions_created
        batch.groups_created = result.groups_created
        batch.members_created = result.members_created
        batch.invalid_rows = result.invalid_rows
        batch.committed_at = datetime.now(timezone.utc)
        batch.raw_payload = {**batch.raw_payload, "rows": [r.model_dump(mode="json") for r in result.rows]}

        await self.imports.flush()
        await self.imports.commit()

        summary = ImportSummary(
            total=len(parsed_rows),
            regions_created=result.regions_created,
            groups_created=result.groups_created,
            members_created=result.members_created,
            regions_skipped=0,
            groups_skipped=0,
            members_skipped=result.members_skipped,
            invalid_rows=result.invalid_rows,
        )
        return ImportPreviewResponse(batch_id=batch.id, summary=summary, rows=result.rows)
