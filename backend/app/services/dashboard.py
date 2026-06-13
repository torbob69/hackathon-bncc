"""
Dashboard aggregation service — computes KPI metrics for the admin dashboard.

All queries are tenant-scoped by koperasi_id (CLAUDE.md §3.2 / §8 requirement).
Money values are returned as Decimal.

Public API:
    compute_dashboard(session, *, koperasi_id) -> DashboardOut
"""
from __future__ import annotations

import logging
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import FarmerStatus, LoanStatus, OrderStatus
from app.models.koperasi import KoperasiFunds
from app.models.loans import Loan
from app.models.orders import Order
from app.models.users import Farmer
from app.schemas.oversight import DashboardOut

logger = logging.getLogger(__name__)

# Statuses that count toward GMV (money has settled or been fulfilled)
_GMV_STATUSES = (OrderStatus.paid, OrderStatus.fulfilled)

# Statuses where a loan has been (or is being) disbursed — counts toward volume
_DISBURSED_LOAN_STATUSES = (
    LoanStatus.active,
    LoanStatus.past_due,
    LoanStatus.paid,
    LoanStatus.seized,
)

# Statuses that represent an active (at-risk) loan portfolio
_ACTIVE_LOAN_STATUSES = (LoanStatus.active, LoanStatus.past_due)

# Non-performing loan statuses (NPL)
_NPL_STATUSES = (LoanStatus.past_due, LoanStatus.seized)

_ZERO = Decimal("0")


async def compute_dashboard(
    session: AsyncSession,
    *,
    koperasi_id: int,
) -> DashboardOut:
    """
    Compute and return dashboard KPIs for *koperasi_id*.

    All aggregations run as a single round-trip each using SQLAlchemy Core
    expressions so they execute as SQL aggregates (not Python loops).

    Returns:
        DashboardOut — populated with Decimal values; rates are fractions [0, 1].
    """

    # ------------------------------------------------------------------
    # 1. GMV — sum of orders.total where status in (paid, fulfilled)
    # ------------------------------------------------------------------
    gmv_result = await session.execute(
        select(
            func.coalesce(
                func.sum(Order.total),
                _ZERO,
            ).label("gmv")
        ).where(
            Order.koperasi_id == koperasi_id,
            Order.status.in_(_GMV_STATUSES),
        )
    )
    gmv: Decimal = gmv_result.scalar_one() or _ZERO

    # ------------------------------------------------------------------
    # 2. Farmer counts
    # ------------------------------------------------------------------
    farmer_counts_result = await session.execute(
        select(
            func.count(Farmer.user_id).label("total"),
            func.count(Farmer.user_id).filter(
                Farmer.status == FarmerStatus.active
            ).label("active"),
        ).where(Farmer.koperasi_id == koperasi_id)
    )
    farmer_row = farmer_counts_result.one()
    total_farmer_count: int = farmer_row.total or 0
    active_farmer_count: int = farmer_row.active or 0

    if total_farmer_count > 0:
        active_farmer_rate = Decimal(active_farmer_count) / Decimal(total_farmer_count)
    else:
        active_farmer_rate = _ZERO

    # ------------------------------------------------------------------
    # 3. Loan portfolio metrics
    # ------------------------------------------------------------------
    loan_result = await session.execute(
        select(
            # Total disbursed principal (all loans that ever reached disbursement)
            func.coalesce(
                func.sum(Loan.principal).filter(
                    Loan.status.in_(_DISBURSED_LOAN_STATUSES)
                ),
                _ZERO,
            ).label("disbursement_volume"),
            # Active loan count (status in active, past_due)
            func.count(Loan.id).filter(
                Loan.status.in_(_ACTIVE_LOAN_STATUSES)
            ).label("active_count"),
            # NPL count (status in past_due, seized)
            func.count(Loan.id).filter(
                Loan.status.in_(_NPL_STATUSES)
            ).label("npl_count"),
        ).where(Loan.koperasi_id == koperasi_id)
    )
    loan_row = loan_result.one()
    loan_disbursement_volume: Decimal = loan_row.disbursement_volume or _ZERO
    active_loan_count: int = loan_row.active_count or 0
    npl_count: int = loan_row.npl_count or 0

    # NPL denominator: active loans + NPL loans (all loans that have been
    # disbursed and are not yet fully paid/rejected).  past_due overlaps with
    # both _ACTIVE_LOAN_STATUSES and _NPL_STATUSES, so we count distinct
    # statuses by querying separately to avoid double-counting.
    #
    # "active" here = LoanStatus.active only (not past_due) because past_due
    # is already counted in npl_count; together they form the denominator.
    #
    # Denominator = COUNT(status in active/past_due/seized) — which equals
    # active_loan_count (active+past_due) MINUS past_due, PLUS npl_count
    # (past_due+seized) = active_only + past_due + seized.
    #
    # Simplest correct formula: denominator = active_loan_count + seized_count
    # where active_loan_count already includes past_due.
    # But npl_count = past_due + seized; active_loan_count = active + past_due.
    # So active_loan_count + npl_count double-counts past_due.
    #
    # Use: denominator = count(status in active/past_due/seized).
    npl_denominator_result = await session.execute(
        select(
            func.count(Loan.id).label("cnt")
        ).where(
            Loan.koperasi_id == koperasi_id,
            Loan.status.in_(
                (LoanStatus.active, LoanStatus.past_due, LoanStatus.seized)
            ),
        )
    )
    npl_denominator: int = npl_denominator_result.scalar_one() or 0

    if npl_denominator > 0:
        npl_rate = Decimal(npl_count) / Decimal(npl_denominator)
    else:
        npl_rate = _ZERO

    # ------------------------------------------------------------------
    # 4. Pool balances from koperasi_funds
    # ------------------------------------------------------------------
    funds_result = await session.execute(
        select(KoperasiFunds).where(
            KoperasiFunds.koperasi_id == koperasi_id
        )
    )
    funds = funds_result.scalar_one_or_none()

    if funds is not None:
        marginal_profit_pool_balance: Decimal = funds.marginal_profit_pool_balance or _ZERO
        loan_pool_balance: Decimal = funds.loan_pool_balance or _ZERO
    else:
        marginal_profit_pool_balance = _ZERO
        loan_pool_balance = _ZERO

    # ------------------------------------------------------------------
    # 5. Assemble and return
    # ------------------------------------------------------------------
    return DashboardOut(
        gmv=gmv,
        active_farmer_count=active_farmer_count,
        total_farmer_count=total_farmer_count,
        active_farmer_rate=active_farmer_rate,
        loan_disbursement_volume=loan_disbursement_volume,
        active_loan_count=active_loan_count,
        npl_count=npl_count,
        npl_rate=npl_rate,
        marginal_profit_pool_balance=marginal_profit_pool_balance,
        loan_pool_balance=loan_pool_balance,
    )
