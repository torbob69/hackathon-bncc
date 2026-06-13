"""
Portfolio reporting service for financing partners.

CLAUDE.md §3.8 / Phase 15 — financing partners receive ONLY the aggregate
fields explicitly granted in their data_share_grants, scoped to the grant's
koperasi_id and date range.

Public API:
    resolve_partner(session, *, user_id) -> FinancingPartner | None
    portfolio_for_partner(session, *, partner) -> list[PortfolioReportOut]

Design rules (CLAUDE.md §8):
  - Auth chain:  JWT.user_id → financing_partners.user_id → data_share_grants
  - Only ACTIVE grants are served; revoked grants yield no data.
  - For each active grant, compute ONLY the metrics in scope_json["fields"],
    filtered to the grant's date range.  NEVER include a field outside scope.
  - scope_json["fields"] is re-validated against ALLOWED_REPORT_FIELDS at read
    time — it is never trusted raw.
  - All metric queries are tenant-scoped by the grant's koperasi_id.
  - Money values are Decimal; rates are Decimal fractions [0, 1].
  - No PII (names, NIK, per-person rows) is ever returned.
"""
from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import FarmerStatus, GrantStatus, LoanStatus, OrderStatus
from app.models.grants import DataShareGrant
from app.models.koperasi import KoperasiFunds
from app.models.loans import Loan
from app.models.orders import Order
from app.models.users import Farmer, FinancingPartner
from app.schemas.reports import ALLOWED_REPORT_FIELDS, PortfolioReportOut

logger = logging.getLogger(__name__)

_ZERO = Decimal("0")

# Mirrors dashboard.py — kept in sync deliberately so report metrics are consistent.
_GMV_STATUSES = (OrderStatus.paid, OrderStatus.fulfilled)
_DISBURSED_LOAN_STATUSES = (
    LoanStatus.active,
    LoanStatus.past_due,
    LoanStatus.paid,
    LoanStatus.seized,
)
_ACTIVE_LOAN_STATUSES = (LoanStatus.active, LoanStatus.past_due)
_NPL_STATUSES = (LoanStatus.past_due, LoanStatus.seized)


# ---------------------------------------------------------------------------
# resolve_partner
# ---------------------------------------------------------------------------


async def resolve_partner(
    session: AsyncSession,
    *,
    user_id: int,
) -> FinancingPartner | None:
    """
    Resolve a FinancingPartner from the authenticated user's user_id.

    Returns the FinancingPartner row if one exists, otherwise None.
    The router maps None → HTTP 403 ("not a registered financing partner").
    """
    result = await session.execute(
        select(FinancingPartner).where(FinancingPartner.user_id == user_id)
    )
    return result.scalar_one_or_none()


# ---------------------------------------------------------------------------
# Internal metric computation helpers (date-range-filtered, tenant-scoped)
# ---------------------------------------------------------------------------


async def _compute_gmv(
    session: AsyncSession,
    *,
    koperasi_id: int,
    date_start: "date",  # noqa: F821
    date_end: "date",  # noqa: F821
) -> Decimal:
    """GMV: sum of orders.total (paid/fulfilled) within the date range."""
    from datetime import date, datetime, timezone

    # Convert to timezone-aware datetimes for the TIMESTAMPTZ column comparison.
    # Use start-of-day UTC for start, end-of-day UTC for end.
    start_dt = datetime(date_start.year, date_start.month, date_start.day, 0, 0, 0, tzinfo=timezone.utc)
    end_dt = datetime(date_end.year, date_end.month, date_end.day, 23, 59, 59, tzinfo=timezone.utc)

    result = await session.execute(
        select(
            func.coalesce(func.sum(Order.total), _ZERO).label("gmv")
        ).where(
            Order.koperasi_id == koperasi_id,
            Order.status.in_(_GMV_STATUSES),
            Order.created_at >= start_dt,
            Order.created_at <= end_dt,
        )
    )
    return result.scalar_one() or _ZERO


async def _compute_farmer_counts(
    session: AsyncSession,
    *,
    koperasi_id: int,
    date_start: "date",  # noqa: F821
    date_end: "date",  # noqa: F821
) -> tuple[int, int, Decimal]:
    """
    Return (total_farmer_count, active_farmer_count, active_farmer_rate).

    Farmer registration date is used for the date range filter (joined within range).
    """
    from datetime import date, datetime, timezone

    start_dt = datetime(date_start.year, date_start.month, date_start.day, 0, 0, 0, tzinfo=timezone.utc)
    end_dt = datetime(date_end.year, date_end.month, date_end.day, 23, 59, 59, tzinfo=timezone.utc)

    result = await session.execute(
        select(
            func.count(Farmer.user_id).label("total"),
            func.count(Farmer.user_id).filter(
                Farmer.status == FarmerStatus.active
            ).label("active"),
        ).where(
            Farmer.koperasi_id == koperasi_id,
            Farmer.created_at >= start_dt,
            Farmer.created_at <= end_dt,
        )
    )
    row = result.one()
    total: int = row.total or 0
    active: int = row.active or 0
    rate = (Decimal(active) / Decimal(total)) if total > 0 else _ZERO
    return total, active, rate


async def _compute_loan_metrics(
    session: AsyncSession,
    *,
    koperasi_id: int,
    date_start: "date",  # noqa: F821
    date_end: "date",  # noqa: F821
) -> tuple[Decimal, int, int, Decimal]:
    """
    Return (loan_disbursement_volume, active_loan_count, npl_count, npl_rate).

    Loans created within the date range are used for the filter.
    """
    from datetime import date, datetime, timezone

    start_dt = datetime(date_start.year, date_start.month, date_start.day, 0, 0, 0, tzinfo=timezone.utc)
    end_dt = datetime(date_end.year, date_end.month, date_end.day, 23, 59, 59, tzinfo=timezone.utc)

    result = await session.execute(
        select(
            func.coalesce(
                func.sum(Loan.principal).filter(Loan.status.in_(_DISBURSED_LOAN_STATUSES)),
                _ZERO,
            ).label("disbursement_volume"),
            func.count(Loan.id).filter(
                Loan.status.in_(_ACTIVE_LOAN_STATUSES)
            ).label("active_count"),
            func.count(Loan.id).filter(
                Loan.status.in_(_NPL_STATUSES)
            ).label("npl_count"),
        ).where(
            Loan.koperasi_id == koperasi_id,
            Loan.created_at >= start_dt,
            Loan.created_at <= end_dt,
        )
    )
    row = result.one()
    disbursement_volume: Decimal = row.disbursement_volume or _ZERO
    active_loan_count: int = row.active_count or 0
    npl_count: int = row.npl_count or 0

    # Denominator: count of loans in (active, past_due, seized) within range.
    denom_result = await session.execute(
        select(func.count(Loan.id).label("cnt")).where(
            Loan.koperasi_id == koperasi_id,
            Loan.status.in_((LoanStatus.active, LoanStatus.past_due, LoanStatus.seized)),
            Loan.created_at >= start_dt,
            Loan.created_at <= end_dt,
        )
    )
    denom: int = denom_result.scalar_one() or 0
    npl_rate = (Decimal(npl_count) / Decimal(denom)) if denom > 0 else _ZERO

    return disbursement_volume, active_loan_count, npl_count, npl_rate


async def _compute_pool_balances(
    session: AsyncSession,
    *,
    koperasi_id: int,
) -> tuple[Decimal, Decimal]:
    """
    Return (marginal_profit_pool_balance, loan_pool_balance) from koperasi_funds.

    Pool balances are point-in-time (current), not date-range-filtered —
    they reflect the live authoritative cached balance.
    """
    result = await session.execute(
        select(KoperasiFunds).where(KoperasiFunds.koperasi_id == koperasi_id)
    )
    funds = result.scalar_one_or_none()
    if funds is None:
        return _ZERO, _ZERO
    return (
        funds.marginal_profit_pool_balance or _ZERO,
        funds.loan_pool_balance or _ZERO,
    )


def _safe_scope_fields(scope_json: dict | None) -> list[str]:
    """
    Extract and re-validate the fields list from scope_json.

    Returns only field names that are in ALLOWED_REPORT_FIELDS.
    Never trusts scope_json raw (CLAUDE.md §8).
    """
    if not scope_json or not isinstance(scope_json, dict):
        return []
    raw_fields = scope_json.get("fields", [])
    if not isinstance(raw_fields, list):
        return []
    return [f for f in raw_fields if isinstance(f, str) and f in ALLOWED_REPORT_FIELDS]


# ---------------------------------------------------------------------------
# portfolio_for_partner
# ---------------------------------------------------------------------------


async def portfolio_for_partner(
    session: AsyncSession,
    *,
    partner: FinancingPartner,
) -> list[PortfolioReportOut]:
    """
    Compute the portfolio report for all ACTIVE grants held by *partner*.

    For each active grant:
      1. Re-validate scope_json["fields"] against ALLOWED_REPORT_FIELDS.
      2. Compute the subset of metrics requested, filtered to the grant's
         koperasi_id and date range.
      3. Return a PortfolioReportOut whose *metrics* dict contains ONLY the
         granted fields.  A field not in scope_json is NEVER included.

    Returns one PortfolioReportOut per granted koperasi (one per active grant).
    An empty list is returned if the partner has no active grants.

    Raises nothing — per-grant errors are logged and that grant is skipped.
    """
    # Find all active grants for this financing partner.
    grants_result = await session.execute(
        select(DataShareGrant).where(
            DataShareGrant.financing_partner_id == partner.id,
            DataShareGrant.status == GrantStatus.active,
        )
    )
    grants: list[DataShareGrant] = list(grants_result.scalars().all())

    if not grants:
        logger.debug("portfolio_for_partner: no active grants for partner id=%d", partner.id)
        return []

    reports: list[PortfolioReportOut] = []

    for grant in grants:
        try:
            allowed_fields = _safe_scope_fields(grant.scope_json)
            if not allowed_fields:
                logger.warning(
                    "portfolio_for_partner: grant id=%d has no valid fields in scope_json, skipping",
                    grant.id,
                )
                continue

            koperasi_id = grant.koperasi_id
            date_start = grant.date_range_start
            date_end = grant.date_range_end

            # Build the metrics dict — compute ONLY what is granted.
            metrics: dict[str, Any] = {}
            field_set = set(allowed_fields)

            # We batch overlapping computations to minimise round-trips.
            needs_gmv = "gmv" in field_set
            needs_farmers = field_set & {
                "active_farmer_count",
                "total_farmer_count",
                "active_farmer_rate",
            }
            needs_loans = field_set & {
                "loan_disbursement_volume",
                "active_loan_count",
                "npl_count",
                "npl_rate",
            }
            needs_pools = field_set & {
                "loan_pool_balance",
                "marginal_profit_pool_balance",
            }

            if needs_gmv:
                metrics["gmv"] = await _compute_gmv(
                    session,
                    koperasi_id=koperasi_id,
                    date_start=date_start,
                    date_end=date_end,
                )

            if needs_farmers:
                total_fc, active_fc, active_fr = await _compute_farmer_counts(
                    session,
                    koperasi_id=koperasi_id,
                    date_start=date_start,
                    date_end=date_end,
                )
                if "total_farmer_count" in field_set:
                    metrics["total_farmer_count"] = total_fc
                if "active_farmer_count" in field_set:
                    metrics["active_farmer_count"] = active_fc
                if "active_farmer_rate" in field_set:
                    metrics["active_farmer_rate"] = active_fr

            if needs_loans:
                disb_vol, active_lc, npl_cnt, npl_r = await _compute_loan_metrics(
                    session,
                    koperasi_id=koperasi_id,
                    date_start=date_start,
                    date_end=date_end,
                )
                if "loan_disbursement_volume" in field_set:
                    metrics["loan_disbursement_volume"] = disb_vol
                if "active_loan_count" in field_set:
                    metrics["active_loan_count"] = active_lc
                if "npl_count" in field_set:
                    metrics["npl_count"] = npl_cnt
                if "npl_rate" in field_set:
                    metrics["npl_rate"] = npl_r

            if needs_pools:
                mp_bal, lp_bal = await _compute_pool_balances(
                    session,
                    koperasi_id=koperasi_id,
                )
                if "marginal_profit_pool_balance" in field_set:
                    metrics["marginal_profit_pool_balance"] = mp_bal
                if "loan_pool_balance" in field_set:
                    metrics["loan_pool_balance"] = lp_bal

            # Final safety gate: strip any key that somehow is not in allowed_fields.
            metrics = {k: v for k, v in metrics.items() if k in field_set}

            reports.append(
                PortfolioReportOut(
                    koperasi_id=koperasi_id,
                    date_range_start=date_start,
                    date_range_end=date_end,
                    metrics=metrics,
                )
            )

        except Exception:
            logger.exception(
                "portfolio_for_partner: error computing report for grant id=%d, skipping",
                grant.id,
            )
            continue

    return reports
