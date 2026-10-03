"""
ImportHistory — one row per Excel Import run (preview and/or commit),
matching the frontend's `processImportRows()` dry-run/commit symmetry.

`raw_payload` stores the classified rows (status: Imported/Skipped/Invalid
+ detail) exactly as the frontend's preview table renders them, so a batch
can be re-displayed or audited after the fact without re-parsing the
original file.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPKMixin



if TYPE_CHECKING:  # pragma: no cover - import cycle guard for relationship types
    from app.models.user import User

class ImportHistory(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "import_history"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False
    )
    uploaded_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="previewed")
    # 'previewed' | 'committed' | 'failed'

    total_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    regions_created: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    groups_created: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    members_created: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    invalid_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    raw_payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    committed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    uploader: Mapped["User"] = relationship()
