"""initial schema

Revision ID: c60bbd8c9359
Revises:
Create Date: 2026-06-13 00:32:17.199261

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'c60bbd8c9359'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- ENUM types (idempotent via DO blocks — CREATE TYPE IF NOT EXISTS is PG16+) ---
    op.execute("""
        DO $$ BEGIN CREATE TYPE user_role AS ENUM ('farmer', 'manager', 'admin', 'distributor', 'financing_partner', 'platform_admin');
        EXCEPTION WHEN duplicate_object THEN NULL; END $$;
    """)
    op.execute("""
        DO $$ BEGIN CREATE TYPE farmer_status AS ENUM ('pending', 'active');
        EXCEPTION WHEN duplicate_object THEN NULL; END $$;
    """)
    op.execute("""
        DO $$ BEGIN CREATE TYPE intake_status AS ENUM ('pending', 'confirmed', 'rejected', 'cancelled');
        EXCEPTION WHEN duplicate_object THEN NULL; END $$;
    """)
    op.execute("""
        DO $$ BEGIN CREATE TYPE stock_direction AS ENUM ('in', 'out');
        EXCEPTION WHEN duplicate_object THEN NULL; END $$;
    """)
    op.execute("""
        DO $$ BEGIN CREATE TYPE order_status AS ENUM ('pending', 'paid', 'fulfilled', 'cancelled');
        EXCEPTION WHEN duplicate_object THEN NULL; END $$;
    """)
    op.execute("""
        DO $$ BEGIN CREATE TYPE fulfillment_type AS ENUM ('delivery', 'pickup');
        EXCEPTION WHEN duplicate_object THEN NULL; END $$;
    """)
    op.execute("""
        DO $$ BEGIN CREATE TYPE payment_channel AS ENUM ('qris', 'va');
        EXCEPTION WHEN duplicate_object THEN NULL; END $$;
    """)
    op.execute("""
        DO $$ BEGIN CREATE TYPE payment_status AS ENUM ('pending', 'paid', 'expired', 'failed');
        EXCEPTION WHEN duplicate_object THEN NULL; END $$;
    """)
    op.execute("""
        DO $$ BEGIN CREATE TYPE ledger_pool AS ENUM ('marginal_profit', 'loan');
        EXCEPTION WHEN duplicate_object THEN NULL; END $$;
    """)
    op.execute("""
        DO $$ BEGIN CREATE TYPE ledger_type AS ENUM ('sale_settlement', 'farmer_payment', 'platform_fee', 'apbn_grant', 'loan_disbursement', 'loan_repayment', 'refund');
        EXCEPTION WHEN duplicate_object THEN NULL; END $$;
    """)
    op.execute("""
        DO $$ BEGIN CREATE TYPE ledger_direction AS ENUM ('credit', 'debit');
        EXCEPTION WHEN duplicate_object THEN NULL; END $$;
    """)
    op.execute("""
        DO $$ BEGIN CREATE TYPE loan_purpose AS ENUM ('benih', 'pupuk', 'alat');
        EXCEPTION WHEN duplicate_object THEN NULL; END $$;
    """)
    op.execute("""
        DO $$ BEGIN CREATE TYPE loan_status AS ENUM ('pending', 'active', 'past_due', 'paid', 'rejected', 'seized');
        EXCEPTION WHEN duplicate_object THEN NULL; END $$;
    """)
    op.execute("""
        DO $$ BEGIN CREATE TYPE installment_status AS ENUM ('unpaid', 'paid', 'late');
        EXCEPTION WHEN duplicate_object THEN NULL; END $$;
    """)
    op.execute("""
        DO $$ BEGIN CREATE TYPE grant_status AS ENUM ('active', 'revoked');
        EXCEPTION WHEN duplicate_object THEN NULL; END $$;
    """)
    op.execute("""
        DO $$ BEGIN CREATE TYPE webhook_status AS ENUM ('received', 'processed', 'duplicate');
        EXCEPTION WHEN duplicate_object THEN NULL; END $$;
    """)
    op.execute("""
        DO $$ BEGIN CREATE TYPE notification_type AS ENUM ('intake_flagged', 'intake_confirmed', 'intake_rejected', 'loan_status');
        EXCEPTION WHEN duplicate_object THEN NULL; END $$;
    """)

    # --- koperasi (tenant root) ---
    op.create_table(
        'koperasi',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('type', sa.String(length=100), nullable=False),
        sa.Column('address', sa.Text(), nullable=False),
        sa.Column('region', sa.String(length=100), nullable=False),
        sa.Column('xendit_account_id', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )

    # --- koperasi_funds (one row per koperasi, locked FOR UPDATE on pool checks) ---
    op.create_table(
        'koperasi_funds',
        sa.Column('koperasi_id', sa.BigInteger(), nullable=False),
        sa.Column('marginal_profit_pool_balance', sa.Numeric(precision=18, scale=2), server_default=sa.text('0'), nullable=False),
        sa.Column('loan_pool_balance', sa.Numeric(precision=18, scale=2), server_default=sa.text('0'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['koperasi_id'], ['koperasi.id']),
        sa.PrimaryKeyConstraint('koperasi_id'),
    )

    # --- xendit_webhook_events (idempotency inbox — no koperasi_id, cross-tenant) ---
    op.create_table(
        'xendit_webhook_events',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('event_id', sa.String(length=128), nullable=False),
        sa.Column('event_type', sa.String(length=100), nullable=False),
        sa.Column('reference_type', sa.String(length=50), nullable=True),
        sa.Column('reference_id', sa.BigInteger(), nullable=True),
        sa.Column('payload', sa.JSON(), nullable=False),
        sa.Column('status', postgresql.ENUM('received', 'processed', 'duplicate', name='webhook_status', create_type=False), nullable=False),
        sa.Column('received_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('processed_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('event_id'),
    )

    # --- users ---
    op.create_table(
        'users',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        # koperasi_id: set for manager/admin only; null for farmer, distributor, financing_partner, platform_admin
        sa.Column('koperasi_id', sa.BigInteger(), nullable=True),
        sa.Column('role', postgresql.ENUM('farmer', 'manager', 'admin', 'distributor', 'financing_partner', 'platform_admin', name='user_role', create_type=False), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('phone', sa.String(length=20), nullable=True),
        sa.Column('password_hash', sa.String(length=255), nullable=False),
        sa.Column('status', sa.String(length=50), server_default='active', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['koperasi_id'], ['koperasi.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email'),
    )
    op.create_index(op.f('ix_users_koperasi_id'), 'users', ['koperasi_id'], unique=False)

    # --- ledger_entries (before tables that FK into it) ---
    op.create_table(
        'ledger_entries',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('koperasi_id', sa.BigInteger(), nullable=False),
        sa.Column('pool', postgresql.ENUM('marginal_profit', 'loan', name='ledger_pool', create_type=False), nullable=False),
        sa.Column('type', postgresql.ENUM('sale_settlement', 'farmer_payment', 'platform_fee', 'apbn_grant', 'loan_disbursement', 'loan_repayment', 'refund', name='ledger_type', create_type=False), nullable=False),
        sa.Column('amount', sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column('direction', postgresql.ENUM('credit', 'debit', name='ledger_direction', create_type=False), nullable=False),
        sa.Column('reference_type', sa.String(length=50), nullable=True),
        sa.Column('reference_id', sa.BigInteger(), nullable=True),
        sa.Column('xendit_disbursement_id', sa.String(length=255), nullable=True),
        sa.Column('external_idempotency_key', sa.String(length=128), nullable=True),
        sa.Column('balance_after', sa.Numeric(precision=18, scale=2), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint(
            "(type IN ('apbn_grant', 'loan_disbursement', 'loan_repayment') AND pool = 'loan')"
            " OR "
            "(type IN ('sale_settlement', 'farmer_payment', 'platform_fee', 'refund') AND pool = 'marginal_profit')",
            name='chk_pool_type',
        ),
        sa.ForeignKeyConstraint(['koperasi_id'], ['koperasi.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_ledger_entries_koperasi_id'), 'ledger_entries', ['koperasi_id'], unique=False)
    op.create_index('ix_ledger_entries_koperasi_created', 'ledger_entries', ['koperasi_id', 'created_at'], unique=False)
    op.create_index(
        'ix_ledger_entries_external_idempotency_key',
        'ledger_entries',
        ['external_idempotency_key'],
        unique=True,
        postgresql_where=sa.text('external_idempotency_key IS NOT NULL'),
    )
    op.create_index(
        'ix_ledger_entries_xendit_disbursement_id',
        'ledger_entries',
        ['xendit_disbursement_id'],
        unique=True,
        postgresql_where=sa.text('xendit_disbursement_id IS NOT NULL'),
    )

    # --- audit_log (append-only; trigger + role revoke added in phase 15) ---
    op.create_table(
        'audit_log',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('koperasi_id', sa.BigInteger(), nullable=True),
        sa.Column('actor_user_id', sa.BigInteger(), nullable=True),
        sa.Column('action', sa.String(length=100), nullable=False),
        sa.Column('entity_type', sa.String(length=100), nullable=False),
        sa.Column('entity_id', sa.BigInteger(), nullable=True),
        sa.Column('before_json', sa.JSON(), nullable=True),
        sa.Column('after_json', sa.JSON(), nullable=True),
        sa.Column('ip', sa.String(length=45), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['actor_user_id'], ['users.id']),
        sa.ForeignKeyConstraint(['koperasi_id'], ['koperasi.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_audit_log_koperasi_id'), 'audit_log', ['koperasi_id'], unique=False)

    # --- commodities ---
    op.create_table(
        'commodities',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('koperasi_id', sa.BigInteger(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('unit', sa.String(length=10), server_default='kg', nullable=False),
        sa.Column('pihps_price', sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column('current_stock_kg', sa.Numeric(precision=10, scale=3), server_default=sa.text('0'), nullable=False),
        sa.Column('cold_storage_location', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['koperasi_id'], ['koperasi.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_commodities_koperasi_id'), 'commodities', ['koperasi_id'], unique=False)

    # --- distributors (cross-tenant) ---
    op.create_table(
        'distributors',
        sa.Column('user_id', sa.BigInteger(), nullable=False),
        sa.Column('company_name', sa.String(length=255), nullable=False),
        sa.Column('address', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('user_id'),
        sa.UniqueConstraint('user_id'),
    )

    # --- farmers ---
    op.create_table(
        'farmers',
        sa.Column('user_id', sa.BigInteger(), nullable=False),
        # canonical tenant for a farmer — single source of truth
        sa.Column('koperasi_id', sa.BigInteger(), nullable=False),
        sa.Column('nik', sa.String(length=16), nullable=False),
        sa.Column('address', sa.Text(), nullable=True),
        sa.Column('ktp_photo_url', sa.Text(), nullable=True),
        sa.Column('credit_tier', sa.String(length=10), nullable=True),
        sa.Column('status', postgresql.ENUM('pending', 'active', name='farmer_status', create_type=False), nullable=False),
        sa.Column('verified_by', sa.BigInteger(), nullable=True),
        sa.Column('verified_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint("nik ~ '^[0-9]{16}$'", name='chk_nik_format'),
        sa.ForeignKeyConstraint(['koperasi_id'], ['koperasi.id']),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.ForeignKeyConstraint(['verified_by'], ['users.id']),
        sa.PrimaryKeyConstraint('user_id'),
        sa.UniqueConstraint('nik'),
        sa.UniqueConstraint('user_id'),
    )
    op.create_index(op.f('ix_farmers_koperasi_id'), 'farmers', ['koperasi_id'], unique=False)

    # --- financing_partners (cross-tenant, login bridge via users) ---
    op.create_table(
        'financing_partners',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.BigInteger(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('contact_email', sa.String(length=255), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id'),
    )

    # --- stock_movements ---
    op.create_table(
        'stock_movements',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('koperasi_id', sa.BigInteger(), nullable=False),
        sa.Column('commodity_id', sa.BigInteger(), nullable=False),
        # direction values: 'in' / 'out'
        sa.Column('direction', postgresql.ENUM('in', 'out', name='stock_direction', create_type=False), nullable=False),
        sa.Column('weight_kg', sa.Numeric(precision=10, scale=3), nullable=False),
        sa.Column('reference_type', sa.String(length=50), nullable=True),
        sa.Column('reference_id', sa.BigInteger(), nullable=True),
        sa.Column('qr_token', sa.Text(), nullable=True),
        sa.Column('created_by', sa.BigInteger(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['commodity_id'], ['commodities.id']),
        sa.ForeignKeyConstraint(['created_by'], ['users.id']),
        sa.ForeignKeyConstraint(['koperasi_id'], ['koperasi.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_stock_movements_koperasi_id'), 'stock_movements', ['koperasi_id'], unique=False)

    # --- notifications ---
    op.create_table(
        'notifications',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('koperasi_id', sa.BigInteger(), nullable=False),
        sa.Column('user_id', sa.BigInteger(), nullable=False),
        sa.Column('type', postgresql.ENUM('intake_flagged', 'intake_confirmed', 'intake_rejected', 'loan_status', name='notification_type', create_type=False), nullable=False),
        sa.Column('reference_type', sa.String(length=50), nullable=True),
        sa.Column('reference_id', sa.BigInteger(), nullable=True),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('is_read', sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['koperasi_id'], ['koperasi.id']),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_notifications_koperasi_id'), 'notifications', ['koperasi_id'], unique=False)
    op.create_index(op.f('ix_notifications_user_id'), 'notifications', ['user_id'], unique=False)

    # --- harvest_intakes ---
    op.create_table(
        'harvest_intakes',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('koperasi_id', sa.BigInteger(), nullable=False),
        sa.Column('farmer_id', sa.BigInteger(), nullable=False),
        sa.Column('commodity_id', sa.BigInteger(), nullable=False),
        sa.Column('weight_kg', sa.Numeric(precision=10, scale=3), nullable=False),
        # JWT-signed payload; Text avoids VARCHAR(255) limit
        sa.Column('qr_token', sa.Text(), nullable=False),
        sa.Column('status', postgresql.ENUM('pending', 'confirmed', 'rejected', 'cancelled', name='intake_status', create_type=False), nullable=False),
        sa.Column('estimated_value', sa.Numeric(precision=18, scale=2), nullable=True),
        sa.Column('exceeds_pool_flag', sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column('reject_reason', sa.Text(), nullable=True),
        # system-set from commodities.pihps_price at confirm — never from request
        sa.Column('price_per_kg', sa.Numeric(precision=18, scale=2), nullable=True),
        sa.Column('total_paid', sa.Numeric(precision=18, scale=2), nullable=True),
        sa.Column('confirmed_by', sa.BigInteger(), nullable=True),
        sa.Column('confirmed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['commodity_id'], ['commodities.id']),
        sa.ForeignKeyConstraint(['confirmed_by'], ['users.id']),
        sa.ForeignKeyConstraint(['farmer_id'], ['farmers.user_id']),
        sa.ForeignKeyConstraint(['koperasi_id'], ['koperasi.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('qr_token'),
    )
    op.create_index(op.f('ix_harvest_intakes_koperasi_id'), 'harvest_intakes', ['koperasi_id'], unique=False)
    op.create_index(op.f('ix_harvest_intakes_farmer_id'), 'harvest_intakes', ['farmer_id'], unique=False)

    # --- data_share_grants ---
    op.create_table(
        'data_share_grants',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('koperasi_id', sa.BigInteger(), nullable=False),
        sa.Column('financing_partner_id', sa.BigInteger(), nullable=False),
        sa.Column('scope_json', sa.JSON(), nullable=False),
        sa.Column('date_range_start', sa.Date(), nullable=False),
        sa.Column('date_range_end', sa.Date(), nullable=False),
        sa.Column('status', postgresql.ENUM('active', 'revoked', name='grant_status', create_type=False), nullable=False),
        sa.Column('granted_by', sa.BigInteger(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['financing_partner_id'], ['financing_partners.id']),
        sa.ForeignKeyConstraint(['granted_by'], ['users.id']),
        sa.ForeignKeyConstraint(['koperasi_id'], ['koperasi.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_data_share_grants_koperasi_id'), 'data_share_grants', ['koperasi_id'], unique=False)
    op.create_index(op.f('ix_data_share_grants_financing_partner_id'), 'data_share_grants', ['financing_partner_id'], unique=False)

    # --- loans ---
    op.create_table(
        'loans',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('koperasi_id', sa.BigInteger(), nullable=False),
        sa.Column('farmer_id', sa.BigInteger(), nullable=False),
        sa.Column('principal', sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column('purpose', postgresql.ENUM('benih', 'pupuk', 'alat', name='loan_purpose', create_type=False), nullable=False),
        sa.Column('installment_months', sa.Integer(), nullable=False),
        sa.Column('interest_rate', sa.Numeric(precision=5, scale=2), nullable=False),
        sa.Column('status', postgresql.ENUM('pending', 'active', 'past_due', 'paid', 'rejected', 'seized', name='loan_status', create_type=False), nullable=False),
        sa.Column('credit_score', sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column('limit_at_application', sa.Numeric(precision=18, scale=2), nullable=True),
        sa.Column('approved_by', sa.BigInteger(), nullable=True),
        sa.Column('disbursed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('xendit_disbursement_id', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['approved_by'], ['users.id']),
        sa.ForeignKeyConstraint(['farmer_id'], ['farmers.user_id']),
        sa.ForeignKeyConstraint(['koperasi_id'], ['koperasi.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('xendit_disbursement_id'),
    )
    op.create_index(op.f('ix_loans_koperasi_id'), 'loans', ['koperasi_id'], unique=False)
    op.create_index(op.f('ix_loans_farmer_id'), 'loans', ['farmer_id'], unique=False)

    # --- orders ---
    op.create_table(
        'orders',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('koperasi_id', sa.BigInteger(), nullable=False),
        sa.Column('distributor_id', sa.BigInteger(), nullable=False),
        sa.Column('status', postgresql.ENUM('pending', 'paid', 'fulfilled', 'cancelled', name='order_status', create_type=False), nullable=False),
        sa.Column('fulfillment_type', postgresql.ENUM('delivery', 'pickup', name='fulfillment_type', create_type=False), nullable=False),
        sa.Column('delivery_address', sa.Text(), nullable=True),
        sa.Column('subtotal', sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column('platform_fee', sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column('total', sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column('xendit_invoice_id', sa.String(length=255), nullable=True),
        sa.Column('payment_channel', postgresql.ENUM('qris', 'va', name='payment_channel', create_type=False), nullable=True),
        sa.Column('payment_status', postgresql.ENUM('pending', 'paid', 'expired', 'failed', name='payment_status', create_type=False), nullable=True),
        # VARCHAR(512) per spec — signed pickup QR token
        sa.Column('pickup_qr_token', sa.String(length=512), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['distributor_id'], ['distributors.user_id']),
        sa.ForeignKeyConstraint(['koperasi_id'], ['koperasi.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('pickup_qr_token'),
        sa.UniqueConstraint('xendit_invoice_id'),
    )
    op.create_index(op.f('ix_orders_koperasi_id'), 'orders', ['koperasi_id'], unique=False)
    op.create_index(op.f('ix_orders_distributor_id'), 'orders', ['distributor_id'], unique=False)

    # --- credit_scores ---
    op.create_table(
        'credit_scores',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('farmer_id', sa.BigInteger(), nullable=False),
        sa.Column('koperasi_id', sa.BigInteger(), nullable=False),
        sa.Column('score', sa.Numeric(precision=5, scale=2), nullable=False),
        sa.Column('tier', sa.String(length=10), nullable=False),
        sa.Column('harvest_weight_6mo', sa.Numeric(precision=10, scale=3), nullable=False),
        sa.Column('txn_count', sa.Integer(), server_default=sa.text('0'), nullable=False),
        sa.Column('active_arrears', sa.Numeric(precision=18, scale=2), server_default=sa.text('0'), nullable=False),
        sa.Column('computed_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['farmer_id'], ['farmers.user_id']),
        sa.ForeignKeyConstraint(['koperasi_id'], ['koperasi.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_credit_scores_farmer_id'), 'credit_scores', ['farmer_id'], unique=False)
    op.create_index(op.f('ix_credit_scores_koperasi_id'), 'credit_scores', ['koperasi_id'], unique=False)
    # Descending composite index — hand-written as raw SQL for reliability
    op.execute("CREATE INDEX ix_credit_scores_farmer_computed ON credit_scores (farmer_id, computed_at DESC)")

    # --- loan_installments ---
    op.create_table(
        'loan_installments',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('loan_id', sa.BigInteger(), nullable=False),
        sa.Column('koperasi_id', sa.BigInteger(), nullable=False),
        sa.Column('due_date', sa.Date(), nullable=False),
        sa.Column('amount_due', sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column('amount_paid', sa.Numeric(precision=18, scale=2), server_default=sa.text('0'), nullable=False),
        sa.Column('status', postgresql.ENUM('unpaid', 'paid', 'late', name='installment_status', create_type=False), nullable=False),
        sa.Column('ledger_entry_id', sa.BigInteger(), nullable=True),
        sa.Column('paid_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['koperasi_id'], ['koperasi.id']),
        sa.ForeignKeyConstraint(['ledger_entry_id'], ['ledger_entries.id']),
        sa.ForeignKeyConstraint(['loan_id'], ['loans.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_loan_installments_koperasi_id'), 'loan_installments', ['koperasi_id'], unique=False)
    op.create_index('ix_loan_installments_loan_due', 'loan_installments', ['loan_id', 'due_date'], unique=False)

    # --- loan_status_history ---
    op.create_table(
        'loan_status_history',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('loan_id', sa.BigInteger(), nullable=False),
        sa.Column('koperasi_id', sa.BigInteger(), nullable=False),
        sa.Column('old_status', postgresql.ENUM('pending', 'active', 'past_due', 'paid', 'rejected', 'seized', name='loan_status', create_type=False), nullable=False),
        sa.Column('new_status', postgresql.ENUM('pending', 'active', 'past_due', 'paid', 'rejected', 'seized', name='loan_status', create_type=False), nullable=False),
        sa.Column('changed_by', sa.BigInteger(), nullable=True),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['changed_by'], ['users.id']),
        sa.ForeignKeyConstraint(['koperasi_id'], ['koperasi.id']),
        sa.ForeignKeyConstraint(['loan_id'], ['loans.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_loan_status_history_koperasi_id'), 'loan_status_history', ['koperasi_id'], unique=False)
    op.create_index(op.f('ix_loan_status_history_loan_id'), 'loan_status_history', ['loan_id'], unique=False)

    # --- order_items ---
    op.create_table(
        'order_items',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('order_id', sa.BigInteger(), nullable=False),
        # koperasi_id for tenant-safe direct queries; service asserts commodity.koperasi_id == orders.koperasi_id
        sa.Column('koperasi_id', sa.BigInteger(), nullable=False),
        sa.Column('commodity_id', sa.BigInteger(), nullable=False),
        sa.Column('weight_kg', sa.Numeric(precision=10, scale=3), nullable=False),
        sa.Column('price_per_kg', sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column('line_total', sa.Numeric(precision=18, scale=2), nullable=False),
        sa.ForeignKeyConstraint(['commodity_id'], ['commodities.id']),
        sa.ForeignKeyConstraint(['koperasi_id'], ['koperasi.id']),
        sa.ForeignKeyConstraint(['order_id'], ['orders.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_order_items_koperasi_id'), 'order_items', ['koperasi_id'], unique=False)
    op.create_index(op.f('ix_order_items_order_id'), 'order_items', ['order_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_order_items_order_id'), table_name='order_items')
    op.drop_index(op.f('ix_order_items_koperasi_id'), table_name='order_items')
    op.drop_table('order_items')
    op.drop_index(op.f('ix_loan_status_history_loan_id'), table_name='loan_status_history')
    op.drop_index(op.f('ix_loan_status_history_koperasi_id'), table_name='loan_status_history')
    op.drop_table('loan_status_history')
    op.drop_index('ix_loan_installments_loan_due', table_name='loan_installments')
    op.drop_index(op.f('ix_loan_installments_koperasi_id'), table_name='loan_installments')
    op.drop_table('loan_installments')
    op.execute("DROP INDEX IF EXISTS ix_credit_scores_farmer_computed")
    op.drop_index(op.f('ix_credit_scores_koperasi_id'), table_name='credit_scores')
    op.drop_index(op.f('ix_credit_scores_farmer_id'), table_name='credit_scores')
    op.drop_table('credit_scores')
    op.drop_index(op.f('ix_orders_distributor_id'), table_name='orders')
    op.drop_index(op.f('ix_orders_koperasi_id'), table_name='orders')
    op.drop_table('orders')
    op.drop_index(op.f('ix_loans_farmer_id'), table_name='loans')
    op.drop_index(op.f('ix_loans_koperasi_id'), table_name='loans')
    op.drop_table('loans')
    op.drop_index(op.f('ix_data_share_grants_financing_partner_id'), table_name='data_share_grants')
    op.drop_index(op.f('ix_data_share_grants_koperasi_id'), table_name='data_share_grants')
    op.drop_table('data_share_grants')
    op.drop_index(op.f('ix_harvest_intakes_farmer_id'), table_name='harvest_intakes')
    op.drop_index(op.f('ix_harvest_intakes_koperasi_id'), table_name='harvest_intakes')
    op.drop_table('harvest_intakes')
    op.drop_index(op.f('ix_stock_movements_koperasi_id'), table_name='stock_movements')
    op.drop_table('stock_movements')
    op.drop_index(op.f('ix_notifications_user_id'), table_name='notifications')
    op.drop_index(op.f('ix_notifications_koperasi_id'), table_name='notifications')
    op.drop_table('notifications')
    op.drop_table('financing_partners')
    op.drop_index(op.f('ix_farmers_koperasi_id'), table_name='farmers')
    op.drop_table('farmers')
    op.drop_table('distributors')
    op.drop_index(op.f('ix_audit_log_koperasi_id'), table_name='audit_log')
    op.drop_table('audit_log')
    op.drop_index('ix_ledger_entries_xendit_disbursement_id', table_name='ledger_entries', postgresql_where=sa.text('xendit_disbursement_id IS NOT NULL'))
    op.drop_index('ix_ledger_entries_external_idempotency_key', table_name='ledger_entries', postgresql_where=sa.text('external_idempotency_key IS NOT NULL'))
    op.drop_index('ix_ledger_entries_koperasi_created', table_name='ledger_entries')
    op.drop_index(op.f('ix_ledger_entries_koperasi_id'), table_name='ledger_entries')
    op.drop_table('ledger_entries')
    op.drop_index(op.f('ix_users_koperasi_id'), table_name='users')
    op.drop_table('users')
    op.drop_table('xendit_webhook_events')
    op.drop_index(op.f('ix_commodities_koperasi_id'), table_name='commodities')
    op.drop_table('commodities')
    op.drop_table('koperasi_funds')
    op.drop_table('koperasi')
    # Drop ENUM types in reverse dependency order
    op.execute("DROP TYPE IF EXISTS notification_type")
    op.execute("DROP TYPE IF EXISTS webhook_status")
    op.execute("DROP TYPE IF EXISTS grant_status")
    op.execute("DROP TYPE IF EXISTS installment_status")
    op.execute("DROP TYPE IF EXISTS loan_status")
    op.execute("DROP TYPE IF EXISTS loan_purpose")
    op.execute("DROP TYPE IF EXISTS ledger_direction")
    op.execute("DROP TYPE IF EXISTS ledger_type")
    op.execute("DROP TYPE IF EXISTS ledger_pool")
    op.execute("DROP TYPE IF EXISTS payment_status")
    op.execute("DROP TYPE IF EXISTS payment_channel")
    op.execute("DROP TYPE IF EXISTS fulfillment_type")
    op.execute("DROP TYPE IF EXISTS order_status")
    op.execute("DROP TYPE IF EXISTS stock_direction")
    op.execute("DROP TYPE IF EXISTS intake_status")
    op.execute("DROP TYPE IF EXISTS farmer_status")
    op.execute("DROP TYPE IF EXISTS user_role")
