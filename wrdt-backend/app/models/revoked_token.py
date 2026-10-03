"""
RevokedToken -- server-side session termination for refresh tokens.

JWTs are stateless, so "logout" with no server state means a stolen
refresh token stays valid for its full lifetime (14 days by default) even
after the user has explicitly signed out. For an application handling
village-level savings ledgers on shared field devices, that is not acceptable:
signing out has to actually end the session.

Design: only the token's `jti` is stored, never the token itself. Access
tokens are intentionally NOT checked against this table on every request
(that would add a database round trip to every call); they are instead
kept short lived, so the worst case after logout is one access-token
lifetime. Rows older than the longest possible refresh lifetime are dead
weight and can be pruned by `scripts/prune_revoked_tokens.py`.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class RevokedToken(Base):
    __tablename__ = "revoked_tokens"
    __table_args__ = (Index("ix_revoked_tokens_expires_at", "expires_at"),)

    jti: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
