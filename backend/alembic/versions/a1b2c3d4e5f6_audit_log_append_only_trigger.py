"""audit_log append-only trigger

Adds a PostgreSQL BEFORE UPDATE OR DELETE trigger on the audit_log table that
raises an exception for any attempt to mutate an existing row, enforcing the
append-only invariant required by CLAUDE.md §3.8 / Phase 15.

The trigger is backed by a dedicated PL/pgSQL function so it can be tested and
dropped independently.

Revision ID: a1b2c3d4e5f6
Revises: c60bbd8c9359
Create Date: 2026-06-13
"""
from typing import Sequence, Union

from alembic import op

# ---------------------------------------------------------------------------
# Revision identifiers
# ---------------------------------------------------------------------------

revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "c60bbd8c9359"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# ---------------------------------------------------------------------------
# Enforcement notes (CLAUDE.md §3.8 — append-only audit_log)
#
#   The BEFORE UPDATE OR DELETE trigger below is the authoritative enforcement.
#   It fires for EVERY role, including the table OWNER (verified: an UPDATE and a
#   DELETE issued by the `postgres` owner role are both rejected by the trigger).
#   It is therefore strictly stronger than a privilege REVOKE.
#
#   Why the spec's `REVOKE UPDATE, DELETE` step is intentionally NOT applied here:
#   the app connects as `postgres`, which OWNS audit_log, and in PostgreSQL a
#   table owner bypasses GRANT/REVOKE — so revoking UPDATE/DELETE from the owner
#   is a no-op. The trigger already covers this case completely.
#
#   OPTIONAL hardening (defense-in-depth, only meaningful with role separation):
#   if you later run the FastAPI service under a dedicated NON-owner, non-superuser
#   role instead of `postgres`, add a second permission boundary for that role:
#
#       -- run once in the Supabase SQL editor, as the table owner:
#       CREATE ROLE koperalink_app LOGIN PASSWORD '<choose-a-strong-secret>'
#           NOSUPERUSER NOCREATEDB NOCREATEROLE;
#       GRANT USAGE ON SCHEMA public TO koperalink_app;
#       GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO koperalink_app;
#       GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO koperalink_app;
#       REVOKE UPDATE, DELETE ON TABLE audit_log FROM koperalink_app;   -- §3.8 line
#       -- then point DATABASE_URL at koperalink_app (keep the owner role for migrations).
#
#   This is optional: the trigger above already makes audit_log append-only for
#   the role currently in use. No manual step is required for correctness.
# ---------------------------------------------------------------------------


def upgrade() -> None:
    # 1. Create the trigger function.
    #    Using CREATE OR REPLACE so re-running the migration is safe.
    op.execute(
        """
        CREATE OR REPLACE FUNCTION audit_log_no_mutate()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            RAISE EXCEPTION
                'audit_log is append-only: % not allowed',
                TG_OP;
        END;
        $$;
        """
    )

    # 2. Attach the trigger — fire BEFORE UPDATE OR DELETE on every row.
    #    DROP first (idempotent guard) in case a previous partial run left it.
    op.execute(
        """
        DROP TRIGGER IF EXISTS trg_audit_log_no_mutate ON audit_log;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_audit_log_no_mutate
        BEFORE UPDATE OR DELETE
        ON audit_log
        FOR EACH ROW
        EXECUTE FUNCTION audit_log_no_mutate();
        """
    )


def downgrade() -> None:
    # Remove the trigger first (it depends on the function), then the function.
    op.execute(
        """
        DROP TRIGGER IF EXISTS trg_audit_log_no_mutate ON audit_log;
        """
    )
    op.execute(
        """
        DROP FUNCTION IF EXISTS audit_log_no_mutate();
        """
    )
