"""
Pydantic v2 schemas for admin funds management and APBN grant endpoints.

All money fields use Decimal — never float (CLAUDE.md §4 fintech convention).
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import LedgerDirection, LedgerPool, LedgerType


class FundsOut(BaseModel):
    """Current pool balances for a koperasi (GET /admin/funds)."""

    model_config = ConfigDict(from_attributes=True)

    koperasi_id: int
    marginal_profit_pool_balance: Decimal
    loan_pool_balance: Decimal
    updated_at: datetime


class ApbnGrantRequest(BaseModel):
    """
    Body for POST /admin/funds/apbn-grant.

    idempotency_key — optional caller-supplied key; if the same key is
    submitted twice the second call returns the original ledger entry
    without creating a duplicate (replay-safe).
    note — freeform memo stored in the audit trail.
    """

    amount: Decimal = Field(..., gt=0, description="Grant amount in IDR (must be > 0)")
    idempotency_key: str | None = Field(
        default=None,
        max_length=128,
        description="Optional idempotency key for replay-safe grant posting",
    )
    note: str | None = Field(
        default=None,
        max_length=500,
        description="Optional memo / reference for the audit trail",
    )


class LedgerEntryOut(BaseModel):
    """Single ledger entry as returned in the admin ledger list and grant response."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    pool: LedgerPool
    type: LedgerType
    amount: Decimal
    direction: LedgerDirection
    reference_type: str | None
    reference_id: int | None
    balance_after: Decimal | None
    created_at: datetime


class ApbnGrantResponse(BaseModel):
    """
    Response for POST /admin/funds/apbn-grant.

    Returns the ledger entry that was created (or the existing one on replay)
    together with the current fund balances so the caller can display both
    in a single round-trip.
    """

    ledger_entry: LedgerEntryOut
    funds: FundsOut
