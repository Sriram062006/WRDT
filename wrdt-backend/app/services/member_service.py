"""
Member service — CRUD + business rules, 1:1 with the frontend's
createMember / updateMember / deleteMember functions:

  - name required, trimmed
  - name uniqueness case-insensitive, scoped to group
  - joined_date defaults to today if not supplied
  - member `code` is auto-generated (group-name initials + zero-padded
    sequence, e.g. "LM001") exactly like the frontend's member-code display
  - seed_* fields are accepted on create ONLY — they exist purely to
    bootstrap meeting #1's opening balances (see Member model docstring);
    they are intentionally NOT editable via update_member's normal fields
    to avoid silently rewriting history once a member has meetings.
  - delete is a soft delete (member remains visible in any locked meeting's
    historical ledger rows; only removed from the currently open meeting's
    ledger by the Meeting Engine service in Phase 5 — MemberService itself
    has no knowledge of meetings)
"""
from __future__ import annotations

import re
import uuid
from datetime import date

from app.core.exceptions import DuplicateError, NotFoundError, ValidationAppError
from app.models.member import Member
from app.repositories.group_repo import GroupRepository
from app.repositories.member_repo import MemberRepository
from app.schemas.member import MemberCreate, MemberRead, MemberUpdate, MemberWithGroup
from app.services.audit_service import AuditService
from app.services.base import BaseService


def _generate_code(group_name: str, sequence: int) -> str:
    initials = "".join(w[0] for w in re.findall(r"[A-Za-z]+", group_name)).upper()[:3] or "MB"
    return f"{initials}{sequence:03d}"


class MemberService(BaseService):
    def __init__(self, db):
        super().__init__(db)
        self.members = MemberRepository(db)
        self.groups = GroupRepository(db)
        self.audit = AuditService(db)

    async def get_or_404(self, member_id: uuid.UUID) -> Member:
        member = await self.members.get(member_id)
        if not member:
            raise NotFoundError("Member not found.")
        return member

    async def list_members(
        self, group_id: uuid.UUID, *, offset: int, limit: int, q: str | None = None
    ) -> tuple[list[Member], int]:
        members = await self.members.list_by_group(group_id, offset=offset, limit=limit, q=q)
        total = await self.members.count_by_group(group_id, q=q)
        return members, total

    async def list_members_for_org(
        self,
        organization_id: uuid.UUID,
        *,
        offset: int,
        limit: int,
        q: str | None = None,
        group_id: uuid.UUID | None = None,
        region_id: uuid.UUID | None = None,
        allowed_group_ids: set[uuid.UUID] | None = None,
    ) -> tuple[list[MemberWithGroup], int]:
        rows = await self.members.list_for_org(
            organization_id, offset=offset, limit=limit, q=q,
            group_id=group_id, region_id=region_id, allowed_group_ids=allowed_group_ids,
        )
        total = await self.members.count_for_org(
            organization_id, q=q, group_id=group_id, region_id=region_id,
            allowed_group_ids=allowed_group_ids,
        )
        items = [
            MemberWithGroup(
                **MemberRead.model_validate(member).model_dump(),
                group_name=group.name,
                region_id=region.id,
                region_name=region.name,
            )
            for member, group, region in rows
        ]
        return items, total

    async def create_member(
        self, group_id: uuid.UUID, payload: MemberCreate, actor_id: uuid.UUID | None
    ) -> Member:
        group = await self.groups.get(group_id)
        if not group:
            raise NotFoundError("Group not found.")

        name = payload.name.strip()
        if not name:
            raise ValidationAppError("Member name is required.")
        if await self.members.get_by_name_ci(group_id, name):
            raise DuplicateError("A member with this name already exists in this group.")

        sequence = await self.members.count_existing_in_group(group_id) + 1
        code = _generate_code(group.name, sequence)

        member = Member(
            group_id=group_id,
            code=code,
            name=name,
            phone=payload.phone,
            joined_date=payload.joined_date or date.today(),
            status="Active",
            seed_prev_saving=payload.seed_prev_saving,
            seed_loan=payload.seed_loan,
            seed_install=payload.seed_install,
            seed_fine=payload.seed_fine,
            created_by=actor_id,
        )
        self.members.add(member)
        await self.members.flush()
        await self.audit.record(
            actor_id=actor_id, action="member.create", entity_type="member",
            entity_id=member.id, after={"name": name, "group_id": str(group_id), "code": code},
        )
        await self.members.commit_refresh(member)

        # If this group currently has an open meeting, sync the new member
        # into it immediately (mirrors the frontend's
        # syncNewMembersIntoOpenLedger). Local import avoids a circular
        # import at module load time (meeting_service -> member repo only,
        # never -> member_service).
        from app.services.meeting_service import MeetingService

        await MeetingService(self.db).sync_new_member_into_open_meeting(group_id, member)

        return member

    async def update_member(
        self, member_id: uuid.UUID, payload: MemberUpdate, actor_id: uuid.UUID | None
    ) -> Member:
        member = await self.get_or_404(member_id)
        before = {"name": member.name, "status": member.status, "phone": member.phone}

        if payload.name is not None:
            name = payload.name.strip()
            if not name:
                raise ValidationAppError("Member name is required.")
            existing = await self.members.get_by_name_ci(member.group_id, name)
            if existing and existing.id != member.id:
                raise DuplicateError("Another member in this group already has this name.")
            member.name = name

        if payload.phone is not None:
            member.phone = payload.phone
        if payload.status is not None:
            member.status = payload.status
        if payload.seed_prev_saving is not None:
            member.seed_prev_saving = payload.seed_prev_saving

        await self.members.flush()
        await self.audit.record(
            actor_id=actor_id, action="member.update", entity_type="member",
            entity_id=member.id, before=before,
            after={"name": member.name, "status": member.status, "phone": member.phone},
        )
        return await self.members.commit_refresh(member)

    async def delete_member(self, member_id: uuid.UUID, actor_id: uuid.UUID | None) -> None:
        member = await self.get_or_404(member_id)
        group_id = member.group_id
        await self.members.delete(member)
        await self.audit.record(
            actor_id=actor_id, action="member.delete", entity_type="member",
            entity_id=member.id, before={"name": member.name},
        )
        await self.members.commit()

        # Mirrors removeMemberFromOpenLedger(): only ever touches the
        # currently-open meeting's row for this member; completed meetings
        # are historical and untouched (also DB-trigger-enforced regardless).
        from app.services.meeting_service import MeetingService

        await MeetingService(self.db).remove_member_from_open_meeting(group_id, member_id)
