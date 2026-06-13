"""user activation flow

Revision ID: f1a2b3c4d5e6
Revises: a1b2c3d4e5f6
Create Date: 2026-06-13

"""
from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op

revision: str = 'f1a2b3c4d5e6'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Drop the existing unique constraint/index on email (was column-level unique=True)
    #    PostgreSQL names column unique constraints as <table>_<col>_key
    op.execute("ALTER TABLE users DROP CONSTRAINT IF EXISTS users_email_key")
    # Also try alembic-generated name variants
    op.execute("DROP INDEX IF EXISTS users_email_key")

    # 2. Make email and password_hash nullable
    op.execute("ALTER TABLE users ALTER COLUMN email DROP NOT NULL")
    op.execute("ALTER TABLE users ALTER COLUMN password_hash DROP NOT NULL")

    # 3. Add new columns
    op.add_column("users", sa.Column("activation_token", sa.String(128), nullable=True))
    op.add_column("users", sa.Column("activation_token_expires_at", sa.DateTime(timezone=True), nullable=True))

    # 4. Create partial unique indexes
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS ix_users_email_unique ON users (email) WHERE email IS NOT NULL")
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS ix_users_phone_unique ON users (phone) WHERE phone IS NOT NULL")
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS ix_users_activation_token_unique ON users (activation_token) WHERE activation_token IS NOT NULL")

    # 5. Add CHECK constraint
    op.execute("ALTER TABLE users ADD CONSTRAINT chk_users_contact CHECK (email IS NOT NULL OR phone IS NOT NULL)")

    # 6. Set existing NULL-password_hash rows to a placeholder (there should be none, but guard)
    #    No action needed — existing rows all have non-null passwords; the column just becomes nullable going forward.


def downgrade() -> None:
    op.execute("ALTER TABLE users DROP CONSTRAINT IF EXISTS chk_users_contact")
    op.execute("DROP INDEX IF EXISTS ix_users_activation_token_unique")
    op.execute("DROP INDEX IF EXISTS ix_users_phone_unique")
    op.execute("DROP INDEX IF EXISTS ix_users_email_unique")
    op.drop_column("users", "activation_token_expires_at")
    op.drop_column("users", "activation_token")
    op.execute("ALTER TABLE users ALTER COLUMN password_hash SET NOT NULL")
    op.execute("ALTER TABLE users ALTER COLUMN email SET NOT NULL")
    op.execute("CREATE UNIQUE INDEX users_email_key ON users (email)")
