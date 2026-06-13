"""
Credit scoring service — pure SQL aggregation, no ML.

Algorithm (CLAUDE.md §3.6):
  Inputs (all tenant-scoped by koperasi_id):
    1. harvest_weight_6mo  — total kg of confirmed intakes in the last 6 months.
    2. txn_count           — number of confirmed intake transactions in the window.
    3. active_arrears      — sum of (amount_due - amount_paid) on unpaid/late
                             installments whose due_date has already passed.

  Weighted score formula (0–100 scale):
    raw = (W_WEIGHT * norm_weight) + (W_TXN * norm_txn) - (W_ARREARS * arrears_penalty)

    Normalisation anchors (tunable constants):
      MAX_WEIGHT_KG = 10_000  kg in 6 months → score contribution capped at 1.0
      MAX_TXN       = 50      transactions   → contribution capped at 1.0
      MAX_ARREARS   = 5_000_000  IDR         → penalty contribution capped at 1.0

    Weights:
      W_WEIGHT  = 40   (40% of score driven by harvest volume)
      W_TXN     = 30   (30% driven by transaction frequency)
      W_ARREARS = 30   (30% penalty for active arrears)

    raw  = clamp(harvest_weight_6mo / MAX_WEIGHT_KG, 0, 1) * W_WEIGHT
         + clamp(txn_count          / MAX_TXN,        0, 1) * W_TXN
         - clamp(active_arrears     / MAX_ARREARS,     0, 1) * W_ARREARS

    score = clamp(raw, 0, 100), stored as Numeric(5,2).

  Tier → credit limit mapping:
    A  (score >= 75)  →  Rp 50,000,000
    B  (score >= 50)  →  Rp 25,000,000
    C  (score >= 25)  →  Rp 10,000,000
    D  (score <  25)  →  Rp  2,000,000

  A fresh CreditScore snapshot row is INSERTed and flushed (not committed —
  caller owns the transaction).  The last snapshot per farmer is retrieved via
  the ix_credit_scores_farmer_computed index (farmer_id, computed_at DESC).

Tenant guarantee:
  Every query in this module carries a koperasi_id filter.  The farmer's
  canonical koperasi is farmers.koperasi_id (CLAUDE.md §8).
"""
from __future__ import annotations

import logging
from datetime import UTC, date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import InstallmentStatus, IntakeStatus
from app.models.intakes import HarvestIntake
from app.models.loans import CreditScore, Loan, LoanInstallment

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Tunable scoring constants (document here so they're easy to find/adjust)
# ---------------------------------------------------------------------------

MAX_WEIGHT_KG: Decimal = Decimal("10000")   # 10 tonnes in 6 months → full weight score
MAX_TXN: Decimal = Decimal("50")            # 50 confirmed intakes  → full txn score
MAX_ARREARS: Decimal = Decimal("5000000")   # Rp 5 jt active arrears → full penalty

W_WEIGHT: Decimal = Decimal("40")           # 40 points for harvest volume
W_TXN: Decimal = Decimal("30")             # 30 points for txn frequency
W_ARREARS: Decimal = Decimal("30")          # 30 points deducted for arrears

# Tier boundaries and credit limits (IDR)
_TIER_THRESHOLDS: list[tuple[Decimal, str, Decimal]] = [
    # (min_score, tier, limit_rp)
    (Decimal("75"), "A", Decimal("50000000.00")),
    (Decimal("50"), "B", Decimal("25000000.00")),
    (Decimal("25"), "C", Decimal("10000000.00")),
    (Decimal("0"),  "D", Decimal("2000000.00")),
]


# ---------------------------------------------------------------------------
# Public helper: tier_to_limit
# ---------------------------------------------------------------------------


def tier_to_limit(tier: str) -> Decimal:
    """
    Return the maximum credit limit (IDR) for a given credit tier string.

    Tier strings are 'A', 'B', 'C', 'D' as produced by compute_credit_score.

    Returns Rp 2,000,000 (tier D limit) for any unrecognised tier as a
    conservative default.
    """
    tier_map: dict[str, Decimal] = {t: lim for _, t, lim in _TIER_THRESHOLDS}
    return tier_map.get(tier, Decimal("2000000.00"))


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _clamp(value: Decimal, lo: Decimal, hi: Decimal) -> Decimal:
    """Clamp *value* to [lo, hi]."""
    return max(lo, min(hi, value))


def _score_to_tier(score: Decimal) -> tuple[str, Decimal]:
    """Map a 0–100 score to (tier, limit)."""
    for threshold, tier, limit in _TIER_THRESHOLDS:
        if score >= threshold:
            return tier, limit
    # Should not reach here given threshold list covers 0+, but be safe.
    return "D", Decimal("2000000.00")


# ---------------------------------------------------------------------------
# Core public function
# ---------------------------------------------------------------------------


async def compute_credit_score(
    session: AsyncSession,
    *,
    koperasi_id: int,
    farmer_id: int,
) -> CreditScore:
    """
    Compute a credit score snapshot for *farmer_id* within *koperasi_id*.

    All queries are tenant-scoped by koperasi_id (CLAUDE.md §8).

    Steps:
      1. Aggregate harvest_weight_6mo and txn_count from confirmed intakes
         in the rolling 6-month window ending now.
      2. Aggregate active_arrears from unpaid/late installments past due.
      3. Apply the weighted formula to produce a 0–100 score.
      4. Map score → tier → limit.
      5. INSERT a CreditScore row, flush (caller commits).

    Returns:
        The flushed CreditScore ORM instance (id populated after flush).
    """
    now_utc = datetime.now(UTC)
    six_months_ago = now_utc - timedelta(days=182)  # ~6 months
    today = date.today()

    # ------------------------------------------------------------------
    # 1. Harvest aggregates — confirmed intakes in the last 6 months
    #    Tenant-scoped: koperasi_id + farmer_id + status=confirmed + window
    # ------------------------------------------------------------------
    harvest_q = await session.execute(
        select(
            func.coalesce(func.sum(HarvestIntake.weight_kg), 0).label("weight_sum"),
            func.count(HarvestIntake.id).label("txn_cnt"),
        ).where(
            and_(
                HarvestIntake.koperasi_id == koperasi_id,
                HarvestIntake.farmer_id == farmer_id,
                HarvestIntake.status == IntakeStatus.confirmed,
                HarvestIntake.confirmed_at >= six_months_ago,
            )
        )
    )
    harvest_row = harvest_q.one()
    harvest_weight_6mo: Decimal = Decimal(str(harvest_row.weight_sum))
    txn_count: int = int(harvest_row.txn_cnt)

    # ------------------------------------------------------------------
    # 2. Active arrears — unpaid/late installments past due date,
    #    joined through loans for tenant scope
    #    Tenant-scoped via LoanInstallment.koperasi_id (denormalized FK)
    # ------------------------------------------------------------------
    arrears_q = await session.execute(
        select(
            func.coalesce(
                func.sum(LoanInstallment.amount_due - LoanInstallment.amount_paid),
                0,
            ).label("arrears_sum")
        )
        .join(Loan, Loan.id == LoanInstallment.loan_id)
        .where(
            and_(
                LoanInstallment.koperasi_id == koperasi_id,
                Loan.farmer_id == farmer_id,
                LoanInstallment.status.in_(
                    [InstallmentStatus.unpaid, InstallmentStatus.late]
                ),
                LoanInstallment.due_date < today,
            )
        )
    )
    arrears_row = arrears_q.one()
    active_arrears: Decimal = Decimal(str(arrears_row.arrears_sum))

    # ------------------------------------------------------------------
    # 3. Weighted score formula (see module docstring for full rationale)
    # ------------------------------------------------------------------
    zero = Decimal("0")
    one = Decimal("1")

    norm_weight: Decimal = _clamp(harvest_weight_6mo / MAX_WEIGHT_KG, zero, one)
    norm_txn: Decimal = _clamp(Decimal(str(txn_count)) / MAX_TXN, zero, one)
    arrears_penalty: Decimal = _clamp(active_arrears / MAX_ARREARS, zero, one)

    raw_score: Decimal = (
        norm_weight * W_WEIGHT
        + norm_txn * W_TXN
        - arrears_penalty * W_ARREARS
    )
    score: Decimal = _clamp(raw_score, zero, Decimal("100")).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )

    # ------------------------------------------------------------------
    # 4. Map to tier and limit
    # ------------------------------------------------------------------
    tier, _limit = _score_to_tier(score)

    # ------------------------------------------------------------------
    # 5. Persist snapshot
    # ------------------------------------------------------------------
    snapshot = CreditScore(
        farmer_id=farmer_id,
        koperasi_id=koperasi_id,
        score=score,
        tier=tier,
        harvest_weight_6mo=harvest_weight_6mo.quantize(
            Decimal("0.001"), rounding=ROUND_HALF_UP
        ),
        txn_count=txn_count,
        active_arrears=active_arrears.quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        ),
        computed_at=now_utc,
    )
    session.add(snapshot)
    await session.flush()  # populate .id; caller owns commit

    logger.info(
        "credit_score: koperasi=%d farmer=%d score=%s tier=%s "
        "harvest_6mo=%s txn=%d arrears=%s snapshot_id=%d",
        koperasi_id,
        farmer_id,
        score,
        tier,
        harvest_weight_6mo,
        txn_count,
        active_arrears,
        snapshot.id,
    )

    return snapshot
