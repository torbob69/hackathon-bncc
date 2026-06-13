import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.enums import InstallmentStatus, LoanPurpose, LoanStatus


class Loan(Base):
    __tablename__ = "loans"

    id: Mapped[int] = mapped_column(sa.BigInteger, primary_key=True, autoincrement=True)
    koperasi_id: Mapped[int] = mapped_column(
        sa.BigInteger, sa.ForeignKey("koperasi.id"), nullable=False, index=True
    )
    farmer_id: Mapped[int] = mapped_column(
        sa.BigInteger, sa.ForeignKey("farmers.user_id"), nullable=False, index=True
    )
    principal: Mapped[sa.Numeric] = mapped_column(
        sa.Numeric(18, 2, asdecimal=True), nullable=False
    )
    purpose: Mapped[LoanPurpose] = mapped_column(
        sa.Enum(LoanPurpose, name="loan_purpose", create_type=True, values_callable=lambda obj: [e.value for e in obj]), nullable=False
    )
    installment_months: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    interest_rate: Mapped[sa.Numeric] = mapped_column(
        sa.Numeric(5, 2, asdecimal=True), nullable=False
    )
    status: Mapped[LoanStatus] = mapped_column(
        sa.Enum(LoanStatus, name="loan_status", create_type=True, values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
        default=LoanStatus.pending,
        server_default="pending",
    )
    credit_score: Mapped[sa.Numeric | None] = mapped_column(
        sa.Numeric(5, 2, asdecimal=True), nullable=True
    )
    limit_at_application: Mapped[sa.Numeric | None] = mapped_column(
        sa.Numeric(18, 2, asdecimal=True), nullable=True
    )
    approved_by: Mapped[int | None] = mapped_column(
        sa.BigInteger, sa.ForeignKey("users.id"), nullable=True
    )
    disbursed_at: Mapped[sa.DateTime | None] = mapped_column(
        sa.DateTime(timezone=True), nullable=True
    )
    xendit_disbursement_id: Mapped[str | None] = mapped_column(
        sa.String(255), nullable=True, unique=True
    )
    created_at: Mapped[sa.DateTime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )


class LoanInstallment(Base):
    __tablename__ = "loan_installments"

    id: Mapped[int] = mapped_column(sa.BigInteger, primary_key=True, autoincrement=True)
    loan_id: Mapped[int] = mapped_column(
        sa.BigInteger, sa.ForeignKey("loans.id"), nullable=False
    )
    # koperasi_id for tenant-safe direct queries
    koperasi_id: Mapped[int] = mapped_column(
        sa.BigInteger, sa.ForeignKey("koperasi.id"), nullable=False, index=True
    )
    due_date: Mapped[sa.Date] = mapped_column(sa.Date, nullable=False)
    amount_due: Mapped[sa.Numeric] = mapped_column(
        sa.Numeric(18, 2, asdecimal=True), nullable=False
    )
    amount_paid: Mapped[sa.Numeric] = mapped_column(
        sa.Numeric(18, 2, asdecimal=True), nullable=False, default=0, server_default=sa.text("0")
    )
    status: Mapped[InstallmentStatus] = mapped_column(
        sa.Enum(InstallmentStatus, name="installment_status", create_type=True, values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
        default=InstallmentStatus.unpaid,
        server_default="unpaid",
    )
    # links to the repayment ledger entry when paid
    ledger_entry_id: Mapped[int | None] = mapped_column(
        sa.BigInteger, sa.ForeignKey("ledger_entries.id"), nullable=True
    )
    paid_at: Mapped[sa.DateTime | None] = mapped_column(
        sa.DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        sa.Index("ix_loan_installments_loan_due", "loan_id", "due_date"),
    )


class LoanStatusHistory(Base):
    __tablename__ = "loan_status_history"

    id: Mapped[int] = mapped_column(sa.BigInteger, primary_key=True, autoincrement=True)
    loan_id: Mapped[int] = mapped_column(
        sa.BigInteger, sa.ForeignKey("loans.id"), nullable=False, index=True
    )
    # koperasi_id for tenant-safe direct queries
    koperasi_id: Mapped[int] = mapped_column(
        sa.BigInteger, sa.ForeignKey("koperasi.id"), nullable=False, index=True
    )
    old_status: Mapped[LoanStatus] = mapped_column(
        sa.Enum(LoanStatus, name="loan_status", create_type=True, values_callable=lambda obj: [e.value for e in obj]), nullable=False
    )
    new_status: Mapped[LoanStatus] = mapped_column(
        sa.Enum(LoanStatus, name="loan_status", create_type=True, values_callable=lambda obj: [e.value for e in obj]), nullable=False
    )
    changed_by: Mapped[int | None] = mapped_column(
        sa.BigInteger, sa.ForeignKey("users.id"), nullable=True
    )
    reason: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    created_at: Mapped[sa.DateTime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )


class CreditScore(Base):
    __tablename__ = "credit_scores"

    id: Mapped[int] = mapped_column(sa.BigInteger, primary_key=True, autoincrement=True)
    farmer_id: Mapped[int] = mapped_column(
        sa.BigInteger, sa.ForeignKey("farmers.user_id"), nullable=False, index=True
    )
    # koperasi_id for tenant-safe direct queries
    koperasi_id: Mapped[int] = mapped_column(
        sa.BigInteger, sa.ForeignKey("koperasi.id"), nullable=False, index=True
    )
    score: Mapped[sa.Numeric] = mapped_column(
        sa.Numeric(5, 2, asdecimal=True), nullable=False
    )
    tier: Mapped[str] = mapped_column(sa.String(10), nullable=False)
    harvest_weight_6mo: Mapped[sa.Numeric] = mapped_column(
        sa.Numeric(10, 3, asdecimal=True), nullable=False
    )
    txn_count: Mapped[int] = mapped_column(sa.Integer, nullable=False, default=0, server_default=sa.text("0"))
    active_arrears: Mapped[sa.Numeric] = mapped_column(
        sa.Numeric(18, 2, asdecimal=True), nullable=False, default=0, server_default=sa.text("0")
    )
    computed_at: Mapped[sa.DateTime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )

    __table_args__ = (
        sa.Index("ix_credit_scores_farmer_computed", "farmer_id", sa.text("computed_at DESC")),
    )
