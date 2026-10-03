"""
Shared FastAPI dependencies: DB session, pagination params, and the
authentication/authorization guards used by every protected route.

Object-level authorization (does this caller own this row?) deliberately
does NOT live here — it needs a database round trip through the entity's
parent chain, so it lives in `app.services.access` and is called
explicitly from each route. Keeping it visible at the call site makes it
obvious when a route forgets it.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthenticationError, PermissionDeniedError
from app.core.security import oauth2_scheme
from app.db.session import get_db
from app.schemas.auth import CurrentUser
from app.services.auth_service import AuthService

DbSession = Annotated[AsyncSession, Depends(get_db)]


@dataclass
class PageParams:
    page: int = 1
    page_size: int = 20
    q: str | None = None

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size


def pagination_params(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    q: str | None = Query(None, max_length=200, description="Free-text search"),
) -> PageParams:
    return PageParams(page=page, page_size=page_size, q=q)


PageParamsDep = Annotated[PageParams, Depends(pagination_params)]


# -- Authentication ------------------------------------------------------
async def get_current_user(
    db: DbSession,
    token: Annotated[str | None, Depends(oauth2_scheme)] = None,
) -> CurrentUser:
    if not token:
        raise AuthenticationError("Not authenticated. Provide a Bearer access token.")
    service = AuthService(db)
    return await service.get_current_user(token)


CurrentUserDep = Annotated[CurrentUser, Depends(get_current_user)]


# -- Authorization (RBAC) ------------------------------------------------
def require_role(*roles: str):
    """Dependency factory: restrict a route to specific role names."""

    def guard(user: CurrentUserDep) -> CurrentUser:
        if user.role_name not in roles:
            raise PermissionDeniedError(
                f"This action requires one of the following roles: {', '.join(roles)}."
            )
        return user

    return guard


def require_permission(permission_key: str):
    """Dependency factory: restrict a route to a specific permission key
    from the role's `permissions` JSONB bag (see scripts/seed_roles.py)."""

    def guard(user: CurrentUserDep) -> CurrentUser:
        if not user.permissions.get(permission_key):
            raise PermissionDeniedError(
                f"This action requires the '{permission_key}' permission."
            )
        return user

    return guard
