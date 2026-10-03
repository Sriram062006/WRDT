from __future__ import annotations

import uuid

from pydantic import BaseModel, EmailStr, Field

from app.schemas.base import TimestampedRead


class UserCreate(BaseModel):
    # organization_id is deliberately absent: it is taken from the
    # authenticated Owner's own token so an account can never be created
    # inside another tenant.
    role_id: uuid.UUID
    email: EmailStr
    password: str = Field(..., min_length=10)
    full_name: str = Field(..., min_length=1, max_length=200)
    phone: str | None = Field(None, max_length=20)


class UserUpdate(BaseModel):
    full_name: str | None = Field(None, min_length=1, max_length=200)
    phone: str | None = Field(None, max_length=20)
    is_active: bool | None = None
    role_id: uuid.UUID | None = None


class PasswordChangeRequest(BaseModel):
    current_password: str = Field(..., min_length=1)
    new_password: str = Field(..., min_length=10, max_length=128)


class PasswordResetRequest(BaseModel):
    new_password: str = Field(..., min_length=10, max_length=128)


class UserRead(TimestampedRead):
    organization_id: uuid.UUID
    role_id: uuid.UUID
    email: EmailStr
    full_name: str
    phone: str | None
    is_active: bool


class UserGroupAssignmentCreate(BaseModel):
    user_id: uuid.UUID
    group_id: uuid.UUID
