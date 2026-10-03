"""
Authentication routes: login, refresh, logout, current-user, and
self-service password change.

RBAC/user-management routes live in users.py -- this file is strictly
"prove who you are" / "who am I" / "change my own password".
"""
from __future__ import annotations

from fastapi import APIRouter, Request, status

from app.api.deps import CurrentUserDep, DbSession
from app.core.exceptions import AppError
from app.core.throttle import login_keys, login_throttle
from app.schemas.auth import LoginRequest, LogoutRequest, MeResponse, RefreshRequest, TokenResponse
from app.schemas.user import PasswordChangeRequest, UserRead
from app.services.auth_service import AuthService
from app.services.user_service import UserService

router = APIRouter()


class TooManyAttemptsError(AppError):
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    error_code = "too_many_attempts"


def _client_ip(request: Request) -> str | None:
    # Behind a reverse proxy the socket address is the proxy's; trust the
    # left-most X-Forwarded-For hop when present. This is only used for
    # throttling, never for authorization, so a spoofed value costs an
    # attacker their own bucket rather than granting access.
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else None


@router.post("/login", response_model=TokenResponse, summary="Login")
async def login(payload: LoginRequest, db: DbSession, request: Request) -> TokenResponse:
    keys = login_keys(payload.email, _client_ip(request))
    wait = login_throttle.retry_after(keys)
    if wait:
        raise TooManyAttemptsError(
            "Too many failed sign-in attempts. Please try again later.",
            details={"retry_after_seconds": wait},
        )

    service = AuthService(db)
    try:
        tokens = await service.authenticate(payload.email, payload.password)
    except AppError:
        login_throttle.record_failure(keys)
        raise
    login_throttle.record_success(keys)
    return tokens


@router.post("/refresh", response_model=TokenResponse, summary="Refresh access token")
async def refresh(payload: RefreshRequest, db: DbSession) -> TokenResponse:
    service = AuthService(db)
    return await service.refresh(payload.refresh_token)


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
    summary="Logout (revokes the refresh token)",
)
async def logout(db: DbSession, payload: LogoutRequest | None = None) -> None:
    """
    Revokes the supplied refresh token server-side so the session cannot
    be resumed. Always returns 204 -- including when no token is supplied
    or it is already invalid -- so clients can call it unconditionally
    while signing out and never get stuck on an error.
    """
    await AuthService(db).logout(payload.refresh_token if payload else None)
    return None


@router.get("/me", response_model=MeResponse, summary="Current authenticated user")
async def me(db: DbSession, current_user: CurrentUserDep) -> MeResponse:
    user_service = UserService(db)
    user = await user_service.get_user_or_404(current_user.id)
    return MeResponse(
        user=UserRead.model_validate(user),
        role=current_user.role_name,
        permissions=current_user.permissions,
        assigned_group_ids=current_user.assigned_group_ids,
    )


@router.post(
    "/change-password",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
    summary="Change my own password",
)
async def change_password(
    payload: PasswordChangeRequest, db: DbSession, current_user: CurrentUserDep
) -> None:
    await UserService(db).change_password(
        current_user.id, payload.current_password, payload.new_password
    )
    return None
