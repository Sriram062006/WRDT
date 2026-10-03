"""
Excel Import routes — Owner-only (matches the permission spec: "Excel
Import" is explicitly an Owner permission, not available to Supervisors).
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, File, UploadFile, status
from fastapi.responses import Response

from app.api.deps import CurrentUserDep, DbSession, require_role
from app.core.exceptions import ValidationAppError
from app.schemas.import_history import ImportPreviewResponse
from app.services.excel_import_service import ExcelImportService

router = APIRouter(dependencies=[Depends(require_role("owner"))])

_MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10MB


@router.get(
    "/template.xlsx",
    summary="Download a blank import template with the expected columns",
    response_class=Response,
)
async def import_template():
    """Staff were guessing the column names from a one-line hint in the
    UI. Shipping the exact template removes that guesswork."""
    content = ExcelImportService.build_template()
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="wrdt_import_template.xlsx"'},
    )


@router.post("/preview", response_model=ImportPreviewResponse, summary="Preview an Excel import (dry run)")
async def preview_import(db: DbSession, current_user: CurrentUserDep, file: UploadFile = File(...)):
    if not file.filename or not file.filename.lower().endswith((".xlsx", ".xlsm")):
        raise ValidationAppError("Only .xlsx/.xlsm files are supported.")

    contents = await file.read()
    if len(contents) > _MAX_UPLOAD_BYTES:
        raise ValidationAppError("File too large (max 10MB).")

    service = ExcelImportService(db)
    return await service.preview_import(current_user.organization_id, contents, file.filename, current_user.id)


@router.post(
    "/{batch_id}/commit",
    response_model=ImportPreviewResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Commit a previously previewed Excel import",
)
async def commit_import(batch_id: uuid.UUID, db: DbSession, current_user: CurrentUserDep):
    service = ExcelImportService(db)
    return await service.commit_import(batch_id, current_user.organization_id, current_user.id)
