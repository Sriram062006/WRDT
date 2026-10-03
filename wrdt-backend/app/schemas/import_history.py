from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel

from app.schemas.base import TimestampedRead


class ImportRowResult(BaseModel):
    """Mirrors the frontend's classified-row shape from processImportRows()."""

    region: str
    group: str
    member: str
    prev_saving: float | None = None
    status: str  # 'Imported' | 'Skipped' | 'Invalid'
    detail: str


class ImportSummary(BaseModel):
    total: int
    regions_created: int
    groups_created: int
    members_created: int
    regions_skipped: int
    groups_skipped: int
    members_skipped: int
    invalid_rows: int


class ImportPreviewResponse(BaseModel):
    batch_id: uuid.UUID
    summary: ImportSummary
    rows: list[ImportRowResult]


class ImportHistoryRead(TimestampedRead):
    organization_id: uuid.UUID
    uploaded_by: uuid.UUID | None
    file_name: str
    status: str
    total_rows: int
    regions_created: int
    groups_created: int
    members_created: int
    invalid_rows: int
    committed_at: datetime | None
