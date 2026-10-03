"""
Centralized application configuration.

All settings are loaded from environment variables (.env in development,
real environment variables in staging/production — never commit a real .env).
Using pydantic-settings gives us validation + type coercion for free, and a
single `get_settings()` accessor that FastAPI can cache via `lru_cache`.
"""
from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── App ──────────────────────────────────────────────────────
    APP_NAME: str = "WRDT Backend"
    APP_ENV: Literal["development", "staging", "production"] = "development"
    APP_DEBUG: bool = True
    API_V1_PREFIX: str = "/api/v1"
    SECRET_KEY: str = Field(..., min_length=16)

    # ── CORS ─────────────────────────────────────────────────────
    CORS_ORIGINS: str = "http://localhost:5173"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    # ── Database ─────────────────────────────────────────────────
    DATABASE_URL: str  # asyncpg DSN, used by the running app
    DATABASE_URL_SYNC: str | None = None  # psycopg2 DSN, used only by Alembic
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20
    DB_POOL_TIMEOUT: int = 30
    DB_ECHO: bool = False
    # Least-privilege Postgres role the API connects as, if one has been
    # created. Used by migration 0004 to harden audit_logs grants. Leave
    # blank (the default) to skip that step -- Supabase projects and local
    # databases usually connect as the owner role.
    APP_DB_ROLE: str = ""
    # Supabase's transaction pooler cannot cache prepared statements;
    # asyncpg must be told so. Set false when pointing at a direct
    # (session-mode) Postgres connection to regain statement caching.
    DB_DISABLE_STATEMENT_CACHE: bool = True

    # ── JWT ──────────────────────────────────────────────────────
    JWT_SECRET_KEY: str = Field(..., min_length=16)
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 14

    # ── Supabase ─────────────────────────────────────────────────
    SUPABASE_URL: str | None = None
    SUPABASE_SERVICE_KEY: str | None = None

    # ── Logging ──────────────────────────────────────────────────
    LOG_LEVEL: str = "INFO"
    LOG_JSON: bool = False

    @property
    def is_production(self) -> bool:
        return self.APP_ENV == "production"


@lru_cache
def get_settings() -> Settings:
    """Cached settings accessor — env is read once per process."""
    return Settings()
