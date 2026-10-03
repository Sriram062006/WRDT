"""
Auth-related Pydantic schemas: request/response bodies for login, refresh,
logout, and the `CurrentUser` object attached to every authenticated
request via `app.api.deps.get_current_user`.

This module must NOT import from `app.api.deps` (or anything under
`app.api`) — deps.py imports from here, so importing back would create a
circular import.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, EmailStr, Field

from app.schemas.user import UserRead


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=1)


class RefreshRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    refresh_token: str | None = None


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    # Lets the client refresh proactively instead of waiting for a 401 in
    # the middle of saving a meeting register.
    expires_at: datetime


class CurrentUser(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    email: EmailStr
    full_name: str
    role_name: str
    permissions: dict[str, Any]
    assigned_group_ids: list[uuid.UUID]


class MeResponse(BaseModel):
    user: UserRead
    role: str
    permissions: dict[str, Any]
    assigned_group_ids: list[uuid.UUID]