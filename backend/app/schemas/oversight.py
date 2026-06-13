"""
Pydantic v2 schemas for admin oversight endpoints.

  AuditLogOut    — read-only view of an audit_log row.
  DashboardOut   — aggregated KPIs for the admin dashboard.

All money fields are Decimal (never float) per CLAUDE.md §4 fintech convention.

active_farmer_rate is expressed as a fraction in [0, 1] (e.g. 0.75 means 75%).
npl_rate is similarly a fraction in [0, 1].
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict


class AuditLogOut(BaseModel):
    """Read-only serialisation of one audit_log row."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    koperasi_id: int | None
    actor_user_id: int | None
    action: str
    entity_type: str
    entity_id: int | None
    before_json: dict[str, Any] | None
    after_json: dict[str, Any] | None
    ip: str | None
    created_at: datetime


class DashboardOut(BaseModel):
    """
    Aggregated KPI snapshot for the admin dashboard.

    Money fields (gmv, loan_disbursement_volume, pool balances) are Decimal.

    Rates (active_farmer_rate, npl_rate) are fractions in [0, 1]:
        - active_farmer_rate = active_farmer_count / total_farmer_count
          (0 when total_farmer_count == 0)
        - npl_rate = npl_count / (active_loan_count + npl_count)
          (0 when no loans exist)
    """

    model_config = ConfigDict(from_attributes=True)

    # GMV: sum of orders.total where status in (paid, fulfilled)
    gmv: Decimal

    # Farmer counts
    active_farmer_count: int
    total_farmer_count: int
    # Fraction [0, 1]
    active_farmer_rate: Decimal

    # Loan portfolio
    loan_disbursement_volume: Decimal
    active_loan_count: int   # status in (active, past_due)
    npl_count: int           # status in (past_due, seized)
    # Fraction [0, 1]
    npl_rate: Decimal

    # Pool balances from koperasi_funds (0 if no row exists)
    marginal_profit_pool_balance: Decimal
    loan_pool_balance: Decimal
