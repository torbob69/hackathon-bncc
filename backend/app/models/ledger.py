import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.enums import LedgerDirection, LedgerPool, LedgerType


class LedgerEntry(Base):
    __tablename__ = "ledger_entries"

    id: Mapped[int] = mapped_column(sa.BigInteger, primary_key=True, autoincrement=True)
    koperasi_id: Mapped[int] = mapped_column(
        sa.BigInteger, sa.ForeignKey("koperasi.id"), nullable=False, index=True
    )
    pool: Mapped[LedgerPool] = mapped_column(
        sa.Enum(LedgerPool, name="ledger_pool", create_type=True, values_callable=lambda obj: [e.value for e in obj]), nullable=False
    )
    type: Mapped[LedgerType] = mapped_column(
        sa.Enum(LedgerType, name="ledger_type", create_type=True, values_callable=lambda obj: [e.value for e in obj]), nullable=False
    )
    amount: Mapped[sa.Numeric] = mapped_column(
        sa.Numeric(18, 2, asdecimal=True), nullable=False
    )
    direction: Mapped[LedgerDirection] = mapped_column(
        sa.Enum(LedgerDirection, name="ledger_direction", create_type=True, values_callable=lambda obj: [e.value for e in obj]), nullable=False
    )
    reference_type: Mapped[str | None] = mapped_column(sa.String(50), nullable=True)
    reference_id: Mapped[int | None] = mapped_column(sa.BigInteger, nullable=True)
    xendit_disbursement_id: Mapped[str | None] = mapped_column(
        sa.String(255), nullable=True
    )
    # unique-where-not-null — partial index defined in __table_args__
    external_idempotency_key: Mapped[str | None] = mapped_column(
        sa.String(128), nullable=True
    )
    # display snapshot only — never the source of truth for balance checks
    balance_after: Mapped[sa.Numeric | None] = mapped_column(
        sa.Numeric(18, 2, asdecimal=True), nullable=True
    )
    created_at: Mapped[sa.DateTime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )

    __table_args__ = (
        # Pool invariant: loan-type entries only touch loan pool; marginal-profit entries only touch marginal_profit pool
        sa.CheckConstraint(
            "(type IN ('apbn_grant', 'loan_disbursement', 'loan_repayment') AND pool = 'loan')"
            " OR "
            "(type IN ('sale_settlement', 'farmer_payment', 'platform_fee', 'refund') AND pool = 'marginal_profit')",
            name="chk_pool_type",
        ),
        # Partial unique indexes — only enforce uniqueness when value is present
        sa.Index(
            "ix_ledger_entries_external_idempotency_key",
            "external_idempotency_key",
            unique=True,
            postgresql_where=sa.text("external_idempotency_key IS NOT NULL"),
        ),
        sa.Index(
            "ix_ledger_entries_xendit_disbursement_id",
            "xendit_disbursement_id",
            unique=True,
            postgresql_where=sa.text("xendit_disbursement_id IS NOT NULL"),
        ),
        # Composite index for tenant-scoped chronological queries
        sa.Index("ix_ledger_entries_koperasi_created", "koperasi_id", "created_at"),
    )
