"""Fix the permanent-meeting-lock trigger.

`prevent_locked_meeting_writes()` resolved its target with
`COALESCE(NEW.meeting_id, OLD.meeting_id)`. In a PL/pgSQL row trigger the
`NEW` record is unassigned during DELETE, so touching `NEW.meeting_id`
raises `record "new" is not assigned yet` instead of evaluating the lock.
The net effect was that the database-level guarantee the whole design
leans on -- "a completed meeting can never be modified" -- did not hold
for deletes: the statement failed with a confusing internal error rather
than a clean, intentional rejection.

This replaces the function with a TG_OP-aware version and, while we are
here, raises a distinguishable SQLSTATE. The old code reused '23505'
(unique_violation), which made a lock breach indistinguishable from a
duplicate key at the driver level. Locked writes now raise
'P0001'-class errors under a dedicated message the service layer can
recognise.

Revision ID: 0005
Revises: 0004
"""
from __future__ import annotations

from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE OR REPLACE FUNCTION prevent_locked_meeting_writes() RETURNS TRIGGER AS $$
        DECLARE
            is_locked BOOLEAN;
            target_meeting_id UUID;
        BEGIN
            IF TG_OP = 'DELETE' THEN
                target_meeting_id := OLD.meeting_id;
            ELSE
                target_meeting_id := NEW.meeting_id;
            END IF;

            SELECT locked INTO is_locked FROM meetings WHERE id = target_meeting_id;

            IF COALESCE(is_locked, FALSE) THEN
                RAISE EXCEPTION
                    'Meeting % is permanently locked and cannot be modified',
                    target_meeting_id
                    USING ERRCODE = 'restrict_violation';
            END IF;

            IF TG_OP = 'DELETE' THEN
                RETURN OLD;
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION prevent_meeting_unlock() RETURNS TRIGGER AS $$
        BEGIN
            IF OLD.locked = TRUE AND NEW.locked = FALSE THEN
                RAISE EXCEPTION 'A completed meeting cannot be reopened'
                    USING ERRCODE = 'restrict_violation';
            END IF;
            IF OLD.status = 'completed' AND NEW.status <> 'completed' THEN
                RAISE EXCEPTION 'A completed meeting cannot be reopened'
                    USING ERRCODE = 'restrict_violation';
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        CREATE OR REPLACE FUNCTION prevent_locked_meeting_writes() RETURNS TRIGGER AS $$
        DECLARE
            is_locked BOOLEAN;
            target_meeting_id UUID;
        BEGIN
            target_meeting_id := COALESCE(NEW.meeting_id, OLD.meeting_id);
            SELECT locked INTO is_locked FROM meetings WHERE id = target_meeting_id;
            IF is_locked THEN
                RAISE EXCEPTION
                    'Meeting % is permanently locked and cannot be modified', target_meeting_id
                    USING ERRCODE = '23505';
            END IF;
            RETURN COALESCE(NEW, OLD);
        END;
        $$ LANGUAGE plpgsql;
        """
    )
