"""Case-insensitive uniqueness — functional unique indexes on lower(name),
matching the frontend's `.toLowerCase()` duplicate-name checks exactly:
  - Region name unique per Organization (case-insensitive)
  - Group name unique per Region (case-insensitive)
  - Member name unique per Group (case-insensitive)

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-10
"""
from __future__ import annotations

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE UNIQUE INDEX uq_region_name_lower_per_org
        ON regions (organization_id, lower(name))
        WHERE deleted_at IS NULL;
    """)
    op.execute("""
        CREATE UNIQUE INDEX uq_group_name_lower_per_region
        ON groups (region_id, lower(name))
        WHERE deleted_at IS NULL;
    """)
    op.execute("""
        CREATE UNIQUE INDEX uq_member_name_lower_per_group
        ON members (group_id, lower(name))
        WHERE deleted_at IS NULL;
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_member_name_lower_per_group;")
    op.execute("DROP INDEX IF EXISTS uq_group_name_lower_per_region;")
    op.execute("DROP INDEX IF EXISTS uq_region_name_lower_per_org;")
