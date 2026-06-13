"""
Pydantic v2 schemas for loan-related endpoints.

Money fields use Decimal (never float) to match the DECIMAL(18,2) columns
and preserve fintech accuracy.  All schema classes use ConfigDict(from_attributes=True)
so they can be constructed directly from SQLAlchemy ORM instances.
"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import InstallmentStatus, LoanPurpose, LoanStatus


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------


class LoanApplyRequest(BaseModel):
    """Body for POST /loans — farmer applies for a new loan."""

    principal: Decimal = Field(
        ...,
        gt=0,
        description="Loan principal amount in IDR (must be > 0). DECIMAL — never float.",
    )
    purpose: LoanPurpose = Field(
        ...,
        description="Purpose of the loan: benih (seeds), pupuk (fertilizer), alat (equipment).",
    )
    installment_months: int = Field(
        ...,
        ge=1,
        description="Repayment period in months (minimum 1).",
    )
    interest_rate: Decimal = Field(
        ...,
        ge=0,
        description="Annual interest rate as a percentage (e.g. 12.00 for 12%). Must be >= 0.",
    )


class RejectRequest(BaseModel):
    """Body for POST /admin/loans/{loan_id}/reject."""

    reason: str = Field(
        ...,
        min_length=3,
        description="Rejection reason (minimum 3 characters).",
    )


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class InstallmentOut(BaseModel):
    """Single loan installment row."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    loan_id: int
    koperasi_id: int
    due_date: date
    amount_due: Decimal
    amount_paid: Decimal
    status: InstallmentStatus
    ledger_entry_id: int | None
    paid_at: datetime | None


class CreditScoreOut(BaseModel):
    """Credit score snapshot for a farmer."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    farmer_id: int
    koperasi_id: int
    score: Decimal
    tier: str
    harvest_weight_6mo: Decimal
    txn_count: int
    active_arrears: Decimal
    computed_at: datetime


class LoanOut(BaseModel):
    """
    Loan summary — used in list responses and as the base for LoanDetailOut.

    All money fields are Decimal to preserve fintech precision.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    koperasi_id: int
    farmer_id: int
    principal: Decimal
    purpose: LoanPurpose
    installment_months: int
    interest_rate: Decimal
    status: LoanStatus
    credit_score: Decimal | None
    limit_at_application: Decimal | None
    approved_by: int | None
    disbursed_at: datetime | None
    xendit_disbursement_id: str | None
    created_at: datetime


class LoanDetailOut(LoanOut):
    """
    Full loan detail — returned by GET /loans/{id} and GET /admin/loans/{id}.

    Adds the installment schedule and the most recent credit score snapshot
    for the farmer (None if no scoring has been run).
    """

    installments: list[InstallmentOut] = Field(default_factory=list)
    latest_credit_score: CreditScoreOut | None = None
