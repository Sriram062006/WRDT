"""
Password hashing + JWT issuing/verification.

Hashing: bcrypt (via passlib). bcrypt has a 72-byte input limit --
`hash_password`/`verify_password` truncate defensively so an unusually
long password can't silently fail instead of raising, matching passlib's
own recommended guard.

Every token carries a `jti` (unique token ID). Access tokens are short
lived and are not checked against storage on each request; refresh tokens
are, so that `POST /auth/logout` genuinely ends a session rather than
merely asking the client to forget it (see `app.models.revoked_token`).
"""
from __future__ import annotations

import hmac
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Literal

from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import get_settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Used only for OpenAPI/Swagger's "Authorize" UI + extracting the bearer
# token from the Authorization header; token validation itself happens in
# api/deps.py's get_current_user, not here.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/v1/auth/login", auto_error=False)

_BCRYPT_MAX_BYTES = 72

# A real bcrypt hash of a random value, used to keep the login path's
# timing roughly constant when the email doesn't exist. Without it,
# "unknown email" returns measurably faster than "wrong password", which
# turns the login endpoint into a user-enumeration oracle.
_DUMMY_HASH = pwd_context.hash(uuid.uuid4().hex)


def hash_password(plain_password: str) -> str:
    truncated = plain_password.encode("utf-8")[:_BCRYPT_MAX_BYTES].decode("utf-8", "ignore")
    return pwd_context.hash(truncated)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    truncated = plain_password.encode("utf-8")[:_BCRYPT_MAX_BYTES].decode("utf-8", "ignore")
    try:
        return pwd_context.verify(truncated, hashed_password)
    except ValueError:
        # Malformed/legacy hash in the row -- treat as a failed login
        # rather than a 500 that reveals the stored value is broken.
        return False


def dummy_verify() -> None:
    """Burn the same work as a real password check. Call on the
    user-not-found branch of login."""
    verify_password("not-a-real-password", _DUMMY_HASH)


def constant_time_equals(a: str, b: str) -> bool:
    return hmac.compare_digest(a.encode("utf-8"), b.encode("utf-8"))


def create_token(
    subject: str,
    token_type: Literal["access", "refresh"],
    extra_claims: dict[str, Any] | None = None,
) -> tuple[str, str, datetime]:
    """Returns (encoded_token, jti, expires_at)."""
    settings = get_settings()
    now = datetime.now(timezone.utc)

    if token_type == "access":
        expire = now + timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    else:
        expire = now + timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS)

    jti = uuid.uuid4().hex
    payload = {
        "sub": subject,
        "type": token_type,
        "jti": jti,
        "iat": now,
        "exp": expire,
        **(extra_claims or {}),
    }
    encoded = jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return encoded, jti, expire


def decode_token(token: str) -> dict[str, Any] | None:
    settings = get_settings()
    try:
        return jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
            options={"require_exp": True, "require_sub": True},
        )
    except JWTError:
        return None
