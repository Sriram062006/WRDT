"""Append-only enforcement for audit_logs.

The application's runtime database role is granted INSERT/SELECT only, so
audit history cannot be altered even by a compromised or buggy API
process.

This originally hard-coded a role name and ran an unconditional REVOKE,
which aborted `alembic upgrade head` with `role "wrdt_app_role" does not
exist` on every environment that had not created that role by hand --
including a stock Supabase project and any local/CI database. The grant
is now:
  * driven by the APP_DB_ROLE setting (empty = skip entirely), and
  * wrapped in a DO block that no-ops when the role is absent,
so migrations always run to completion and hardening is applied wherever
the role genuinely exists.

Revision ID: 0004
Revises: 0003
"""
from __future__ import annotations

from alembic import op

from app.core.config import get_settings

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def _role() -> str:
    return (get_settings().APP_DB_ROLE or "").strip()


def upgrade() -> None:
    role = _role()
    if not role:
        return
    op.execute(
        f"""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{role}') THEN
                REVOKE UPDATE, DELETE ON audit_logs FROM "{role}";
                GRANT INSERT, SELECT ON audit_logs TO "{role}";
            ELSE
                RAISE NOTICE
                    'Role % not found; skipping audit_logs grant hardening.', '{role}';
            END IF;
        END
        $$;
        """
    )


def downgrade() -> None:
    role = _role()
    if not role:
        return
    op.execute(
        f"""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{role}') THEN
                GRANT UPDATE, DELETE ON audit_logs TO "{role}";
            END IF;
        END
        $$;
        """
    )
