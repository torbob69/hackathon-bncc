"""
Pydantic v2 schemas for koperasi onboarding and profile endpoints.

Money fields use Decimal — never float (CLAUDE.md §4 fintech convention).
KoperasiOut is safe to expose; it does not include internal secrets beyond
xendit_account_id (needed by platform_admin operators).
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------


class KoperasiCreate(BaseModel):
    """
    Body for POST /koperasi — platform_admin creates a new tenant.

    xendit_account_id is optional at creation time; it can be patched later
    once the koperasi has completed Xendit onboarding.
    """

    name: str = Field(..., min_length=1, max_length=255, description="Koperasi display name")
    type: str = Field(..., min_length=1, max_length=100, description="Koperasi type (e.g. KSP, KUD)")
    address: str = Field(..., min_length=1, description="Full address")
    region: str = Field(..., min_length=1, max_length=100, description="Region / province")
    xendit_account_id: str | None = Field(
        default=None,
        max_length=255,
        description="Xendit sub-account ID (set after Xendit onboarding; optional at creation)",
    )


class KoperasiUpdate(BaseModel):
    """
    Body for PATCH /koperasi/{koperasi_id} — all fields optional.

    Only supplied fields are applied; None means 'leave unchanged'.
    """

    name: str | None = Field(default=None, min_length=1, max_length=255)
    type: str | None = Field(default=None, min_length=1, max_length=100)
    address: str | None = Field(default=None, min_length=1)
    region: str | None = Field(default=None, min_length=1, max_length=100)
    xendit_account_id: str | None = Field(default=None, max_length=255)


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class KoperasiOut(BaseModel):
    """Single koperasi row — returned by all koperasi read endpoints."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    type: str
    address: str
    region: str
    xendit_account_id: str | None
    created_at: datetime


class KoperasiFundsOut(BaseModel):
    """Pool balances for a koperasi — returned by /me/profile and fund endpoints."""

    model_config = ConfigDict(from_attributes=True)

    koperasi_id: int
    marginal_profit_pool_balance: Decimal
    loan_pool_balance: Decimal
    updated_at: datetime


class KoperasiWithFundsOut(BaseModel):
    """
    Combined koperasi profile + fund balances.

    Returned by GET /koperasi/me/profile so the caller gets koperasi
    metadata and pool balances in a single response.
    """

    koperasi: KoperasiOut
    funds: KoperasiFundsOut
