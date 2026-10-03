"""
Authentication service -- login, token refresh, logout, and the
current-user lookup used by every protected route.

Session termination: refresh tokens carry a `jti` and are checked against
the `revoked_tokens` table, so `POST /auth/logout` genuinely ends the
session instead of merely asking the client to forget its tokens. Access
tokens are not checked per request (that would add a query to every call)
and are therefore kept short lived -- the exposure window after logout is
at most `JWT_ACCESS_TOKEN_EXPIRE_MINUTES`.

Brute-force resistance: repeated failed logins for the same email or from
the same client address are throttled in-process (see
`app.core.throttle`). That is sufficient for a single-instance
deployment; a multi-instance deployment should move the counter to Redis,
which is why the throttle is behind its own small module.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import delete, select

from app.core.exceptions import AuthenticationError
from app.core.security import create_token, decode_token, dummy_verify, verify_password
from app.models.revoked_token import RevokedToken
from app.repositories.role_repo import RoleRepository
from app.repositories.user_repo import UserRepository
from app.schemas.auth import CurrentUser, TokenResponse
from app.services.base import BaseService


class AuthService(BaseService):
    def __init__(self, db):
        super().__init__(db)
        self.users = UserRepository(db)
        self.roles = RoleRepository(db)

    async def authenticate(self, email: str, password: str) -> TokenResponse:
        user = await self.users.get_by_email(email)
        if not user:
            # Same error text AND similar timing as a wrong password, so
            # the endpoint can't be used to enumerate valid accounts.
            dummy_verify()
            raise AuthenticationError("Incorrect email or password.")
        if not verify_password(password, user.password_hash):
            raise AuthenticationError("Incorrect email or password.")
        if not user.is_active:
            raise AuthenticationError("This account has been deactivated.")

        return await self._issue_tokens(user)

    async def refresh(self, refresh_token: str) -> TokenResponse:
        payload = decode_token(refresh_token)
        if not payload or payload.get("type") != "refresh":
            raise AuthenticationError("Invalid or expired refresh token.")

        jti = payload.get("jti")
        if jti and await self._is_revoked(jti):
            raise AuthenticationError("This session has been signed out.")

        user_id = payload.get("sub")
        user = await self.users.get(uuid.UUID(user_id)) if user_id else None
        if not user or not user.is_active:
            raise AuthenticationError("Invalid or expired refresh token.")

        # Rotate: the presented refresh token is burned as it is exchanged,
        # so a leaked copy can be used at most once and its reuse is
        # rejected rather than silently accepted alongside the real one.
        if jti:
            await self._revoke(jti, user.id, payload.get("exp"))

        tokens = await self._issue_tokens(user)
        await self.db.commit()
        return tokens

    async def logout(self, refresh_token: str | None) -> None:
        if not refresh_token:
            return
        payload = decode_token(refresh_token)
        if not payload:
            return  # already unusable; nothing to revoke
        jti = payload.get("jti")
        sub = payload.get("sub")
        if jti:
            await self._revoke(jti, uuid.UUID(sub) if sub else None, payload.get("exp"))
            await self.db.commit()

    async def get_current_user(self, access_token: str) -> CurrentUser:
        payload = decode_token(access_token)
        if not payload or payload.get("type") != "access":
            raise AuthenticationError("Invalid or expired access token.")

        user_id = payload.get("sub")
        if not user_id:
            raise AuthenticationError("Invalid or expired access token.")
        try:
            parsed_id = uuid.UUID(user_id)
        except (ValueError, TypeError):
            raise AuthenticationError("Invalid or expired access token.")

        # Role, organization and active flag are re-read from the database
        # on every request rather than trusted from the token's claims, so
        # a demotion or deactivation takes effect immediately instead of
        # at the next token expiry.
        user = await self.users.get_with_role(parsed_id)
        if not user or not user.is_active:
            raise AuthenticationError("Invalid or expired access token.")

        assigned_group_ids = await self.users.get_assigned_group_ids(user.id)

        return CurrentUser(
            id=user.id,
            organization_id=user.organization_id,
            email=user.email,
            full_name=user.full_name,
            role_name=user.role.name,
            permissions=user.role.permissions or {},
            assigned_group_ids=assigned_group_ids,
        )

    # -- internals -------------------------------------------------------
    async def _issue_tokens(self, user) -> TokenResponse:
        role = await self.roles.get(user.role_id)
        claims = {"org": str(user.organization_id), "role": role.name if role else None}
        access_token, _, access_exp = create_token(str(user.id), "access", claims)
        refresh_token, _, _ = create_token(str(user.id), "refresh", claims)
        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_at=access_exp,
        )

    async def _is_revoked(self, jti: str) -> bool:
        stmt = select(RevokedToken.jti).where(RevokedToken.jti == jti)
        return (await self.db.execute(stmt)).scalar_one_or_none() is not None

    async def _revoke(self, jti: str, user_id: uuid.UUID | None, exp: int | None) -> None:
        expires_at = (
            datetime.fromtimestamp(exp, tz=timezone.utc) if exp else datetime.now(timezone.utc)
        )
        if await self._is_revoked(jti):
            return
        self.db.add(RevokedToken(jti=jti, user_id=user_id, expires_at=expires_at))
        # Opportunistic cleanup: rows past their own expiry can never match
        # a still-valid token again, so the table stays bounded without a
        # separate cron job being mandatory.
        await self.db.execute(
            delete(RevokedToken).where(RevokedToken.expires_at < datetime.now(timezone.utc))
        )
