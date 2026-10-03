"""
FastAPI application factory.

Kept intentionally thin: configuration, middleware, exception handlers, and
routers are all assembled from their own modules so `main.py` stays a
readable table of contents for the whole app rather than a dumping ground.
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.exceptions import register_exception_handlers
from app.core.logging_config import configure_logging, get_logger
from app.core.middleware import (
    RequestContextMiddleware,
    SecurityHeadersMiddleware,
    TimingMiddleware,
)
from app.db.session import engine

settings = get_settings()
configure_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("app_startup", env=settings.APP_ENV)
    _assert_production_secrets(settings)
    yield
    logger.info("app_shutdown")
    await engine.dispose()


# Placeholder values that ship in .env.example. If any of them survive
# into a production boot the deployment is signing tokens with a public
# secret, so refuse to start rather than run insecurely and silently.
_PLACEHOLDER_SECRETS = {
    "change-me-to-a-long-random-string",
    "change-me-to-a-different-long-random-string",
    "change-me",
    "secret",
    "changeme",
}


def _assert_production_secrets(settings) -> None:
    if not settings.is_production:
        return
    problems = []
    if settings.SECRET_KEY.strip().lower() in _PLACEHOLDER_SECRETS:
        problems.append("SECRET_KEY is still the example placeholder")
    if settings.JWT_SECRET_KEY.strip().lower() in _PLACEHOLDER_SECRETS:
        problems.append("JWT_SECRET_KEY is still the example placeholder")
    if settings.SECRET_KEY == settings.JWT_SECRET_KEY:
        problems.append("SECRET_KEY and JWT_SECRET_KEY must be different values")
    if settings.APP_DEBUG:
        problems.append("APP_DEBUG must be false in production")
    if any(o.strip() == "*" for o in settings.cors_origins_list):
        problems.append("CORS_ORIGINS must not be '*' when credentials are allowed")
    if problems:
        raise RuntimeError(
            "Refusing to start in production with an insecure configuration: "
            + "; ".join(problems)
        )


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.APP_NAME,
        version="1.0.0",
        description=(
            "WRDT backend API — supports the existing WRDT v1.0 frontend "
            "(Regions, Groups, Members, Meeting Register, Loan Workflow, "
            "Excel Import) exactly as designed, with no business-rule changes."
        ),
        # Swagger/OpenAPI is disabled in production to avoid exposing the full
        # schema publicly; enable behind auth/VPN if needed post-launch.
        docs_url="/docs" if not settings.is_production else None,
        redoc_url="/redoc" if not settings.is_production else None,
        openapi_url="/openapi.json" if not settings.is_production else None,
        lifespan=lifespan,
    )

    # ── Middleware (order matters: outermost added last executes first) ────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID", "X-Process-Time-Ms"],
    )
    app.add_middleware(SecurityHeadersMiddleware, is_production=settings.is_production)
    app.add_middleware(TimingMiddleware)
    app.add_middleware(RequestContextMiddleware)

    register_exception_handlers(app)

    app.include_router(api_router, prefix=settings.API_V1_PREFIX)

    @app.get("/", include_in_schema=False)
    async def root() -> dict:
        return {"service": settings.APP_NAME, "api": settings.API_V1_PREFIX, "status": "ok"}

    return app


app = create_app()
