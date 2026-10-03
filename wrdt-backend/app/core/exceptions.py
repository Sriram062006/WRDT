"""
Application-wide exception hierarchy + FastAPI exception handlers.

Business/domain code should raise these instead of raw HTTPException, so
that:
  1. Service and repository layers stay framework-agnostic (no FastAPI
     import needed to raise a domain error).
  2. Every error response has a consistent JSON shape across the whole API.
  3. The permanent-lock rule, duplicate-name rules, etc. all surface as
     clearly named exception types that unit tests can assert on directly.
"""
from __future__ import annotations

from fastapi import Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.logging_config import get_logger

logger = get_logger(__name__)


class AppError(Exception):
    """Base class for all application-raised errors."""

    status_code: int = status.HTTP_400_BAD_REQUEST
    error_code: str = "app_error"

    def __init__(self, message: str, *, details: dict | None = None):
        self.message = message
        self.details = details or {}
        super().__init__(message)


class NotFoundError(AppError):
    status_code = status.HTTP_404_NOT_FOUND
    error_code = "not_found"


class DuplicateError(AppError):
    """Name-uniqueness violations (region/group/member scoped uniqueness)."""

    status_code = status.HTTP_409_CONFLICT
    error_code = "duplicate"


class ValidationAppError(AppError):
    status_code = 422
    error_code = "validation_error"


class PermissionDeniedError(AppError):
    status_code = status.HTTP_403_FORBIDDEN
    error_code = "permission_denied"


class AuthenticationError(AppError):
    status_code = status.HTTP_401_UNAUTHORIZED
    error_code = "authentication_error"


class MeetingLockedError(AppError):
    """
    Raised when any write is attempted against a completed/locked meeting.
    This mirrors (at the service layer) the same rule the database enforces
    via triggers — belt-and-braces, so the API can return a clean 409
    instead of surfacing a raw database error.
    """

    status_code = status.HTTP_409_CONFLICT
    error_code = "meeting_locked"


class SequenceViolationError(AppError):
    """
    Raised when an operation would violate the "one open meeting per group"
    or "meetings must be completed in order" rules.
    """

    status_code = status.HTTP_409_CONFLICT
    error_code = "sequence_violation"


def _jsonable(value):
    """Make a pydantic error payload JSON-encodable.

    `exc.errors()` embeds the offending input and the constraint context
    verbatim. For a money field those are `Decimal` objects, which the
    JSON encoder cannot serialise -- so rejecting a negative amount
    raised a TypeError inside the error handler and the client received
    an opaque 500 instead of the 422 explaining what was wrong. Anything
    non-primitive is coerced to its string form.
    """
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _error_response(status_code: int, error_code: str, message: str, details: dict | None = None):
    return JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "code": error_code,
                "message": message,
                "details": _jsonable(details or {}),
            }
        },
    )


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    logger.warning(
        "app_error",
        path=request.url.path,
        error_code=exc.error_code,
        message=exc.message,
    )
    return _error_response(exc.status_code, exc.error_code, exc.message, exc.details)


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    errors = _jsonable(exc.errors())
    logger.warning("validation_error", path=request.url.path, errors=errors)
    return _error_response(
        422,
        "validation_error",
        "Request validation failed.",
        details={"errors": errors},
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.error("unhandled_exception", path=request.url.path, exc_info=exc)
    return _error_response(
        status.HTTP_500_INTERNAL_SERVER_ERROR,
        "internal_server_error",
        "An unexpected error occurred.",
    )


def register_exception_handlers(app) -> None:
    app.add_exception_handler(AppError, app_error_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
