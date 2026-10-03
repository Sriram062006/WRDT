"""One-open-meeting-per-group constraint + the permanent meeting lock,
enforced as hard database guarantees (not just application checks):

  1. Partial unique index: at most one meeting with status='in_progress'
     per group at any time — the DB-level version of the frontend's
     startNewMeetingForGroup() sequencing rule.
  2. BEFORE INSERT/UPDATE/DELETE trigger on meeting_entries and expenses:
     rejects any write once the parent meeting is locked. Mirrors (and
     strengthens) the frontend's own comment: "the lock is permanent, even
     against bugs elsewhere in the app trying to call this again."
  3. BEFORE UPDATE trigger on meetings: rejects flipping `locked` from
     TRUE back to FALSE — a completed meeting can never be reopened.

Revision ID: 0003
Revises: 0002
Create Date: 2026-07-10
"""
from __future__ import annotations

from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # (1) one open meeting per group
    op.execute("""
        CREATE UNIQUE INDEX uq_one_open_meeting_per_group
        ON meetings (group_id)
        WHERE status = 'in_progress';
    """)

    # (2) reject writes to locked meetings' entries/expenses
    op.execute("""
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
    """)

    op.execute("""
        CREATE TRIGGER trg_lock_meeting_entries
        BEFORE INSERT OR UPDATE OR DELETE ON meeting_entries
        FOR EACH ROW EXECUTE FUNCTION prevent_locked_meeting_writes();
    """)

    op.execute("""
        CREATE TRIGGER trg_lock_expenses
        BEFORE INSERT OR UPDATE OR DELETE ON expenses
        FOR EACH ROW EXECUTE FUNCTION prevent_locked_meeting_writes();
    """)

    # (3) a locked meeting can never be reopened
    op.execute("""
        CREATE OR REPLACE FUNCTION prevent_meeting_unlock() RETURNS TRIGGER AS $$
        BEGIN
            IF OLD.locked = TRUE AND NEW.locked = FALSE THEN
                RAISE EXCEPTION 'A completed meeting cannot be reopened' USING ERRCODE = '23505';
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)

    op.execute("""
        CREATE TRIGGER trg_meeting_no_unlock
        BEFORE UPDATE ON meetings
        FOR EACH ROW EXECUTE FUNCTION prevent_meeting_unlock();
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_meeting_no_unlock ON meetings;")
    op.execute("DROP FUNCTION IF EXISTS prevent_meeting_unlock();")
    op.execute("DROP TRIGGER IF EXISTS trg_lock_expenses ON expenses;")
    op.execute("DROP TRIGGER IF EXISTS trg_lock_meeting_entries ON meeting_entries;")
    op.execute("DROP FUNCTION IF EXISTS prevent_locked_meeting_writes();")
    op.execute("DROP INDEX IF EXISTS uq_one_open_meeting_per_group;")
