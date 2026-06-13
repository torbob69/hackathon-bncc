"""
Anomaly / fraud-detection service — Phase 15 (CLAUDE.md §3.8).

Heuristic checks over audit_log, ledger_entries, and harvest_intakes to surface
suspicious patterns for admin review.  All checks are READ-ONLY (no writes).
All queries are tenant-scoped by koperasi_id.

Public API:
    detect_anomalies(session, *, koperasi_id) -> list[AnomalyOut]

Implemented heuristics
----------------------
(A) ORPHAN_DEBIT — ledger_entries rows where direction='debit' and reference_id
    IS NULL.  Every debit should reference a business event (harvest payment,
    loan disbursement, etc.).  A null reference_id on a debit indicates a
    potentially unauthorised or corrupt ledger write.

(B) PIHPS_PRICE_DEVIATION — harvest_intakes.confirmed rows where price_per_kg
    does not equal the current commodities.pihps_price for that commodity.
    Prices are system-locked at confirm time (CLAUDE.md §3.5 / §8).  Any
    deviation is suspicious and should be investigated.

(C) LARGE_LEDGER_ENTRY — single debit ledger entries whose amount exceeds
    5× the median debit amount for that koperasi.  Statistically unusual large
    movements may indicate a disbursement error or fraud.

(D) RAPID_FIRE_CONFIRMS — multiple harvest_intakes confirmed by the same
    manager (confirmed_by) within any rolling 5-minute window (≥3 confirms).
    Rapid-fire confirmations by a single actor are a kasir fraud signal
    (rubber-stamping without actually re-weighing).

Each heuristic is independent.  The list is concatenated and returned sorted by
created_at descending.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.commodities import Commodity
from app.models.enums import IntakeStatus, LedgerDirection
from app.models.intakes import HarvestIntake
from app.models.ledger import LedgerEntry
from app.schemas.reports import AnomalyOut

logger = logging.getLogger(__name__)

_ZERO = Decimal("0")

# Multiplier above which a single debit is flagged as "large".
_LARGE_ENTRY_MULTIPLIER = Decimal("5")

# Minimum confirms within the time window to trigger the rapid-fire check.
_RAPID_FIRE_THRESHOLD = 3

# Rolling time window (minutes) for the rapid-fire check.
_RAPID_FIRE_WINDOW_MINUTES = 5


# ---------------------------------------------------------------------------
# (A) Orphan debit entries
# ---------------------------------------------------------------------------


async def _check_orphan_debits(
    session: AsyncSession,
    *,
    koperasi_id: int,
) -> list[AnomalyOut]:
    """
    Heuristic A: debit ledger entries with reference_id IS NULL.

    Every legitimate debit is produced by a confirmed business event and carries
    a reference_id pointing to the originating row (harvest_intake id, order id,
    loan id, etc.).  A null reference_id on a debit has no business explanation.
    """
    result = await session.execute(
        select(LedgerEntry).where(
            LedgerEntry.koperasi_id == koperasi_id,
            LedgerEntry.direction == LedgerDirection.debit,
            LedgerEntry.reference_id.is_(None),
        ).order_by(LedgerEntry.created_at.desc()).limit(50)
    )
    entries = result.scalars().all()

    anomalies: list[AnomalyOut] = []
    for entry in entries:
        anomalies.append(
            AnomalyOut(
                type="orphan_debit",
                severity="high",
                entity_type="ledger_entries",
                entity_id=entry.id,
                detail=(
                    f"Debit ledger entry id={entry.id} "
                    f"(pool={entry.pool.value}, type={entry.type.value}, "
                    f"amount={entry.amount}) has no reference_id. "
                    "All legitimate debits must reference a business event."
                ),
                created_at=entry.created_at,
            )
        )
    return anomalies


# ---------------------------------------------------------------------------
# (B) PIHPS price deviations on confirmed intakes
# ---------------------------------------------------------------------------


async def _check_pihps_deviations(
    session: AsyncSession,
    *,
    koperasi_id: int,
) -> list[AnomalyOut]:
    """
    Heuristic B: confirmed harvest_intakes where price_per_kg != pihps_price.

    price_per_kg is system-set from commodities.pihps_price at confirmation
    time and must never be modified.  Any confirmed intake whose stored
    price_per_kg diverges from the commodity's current pihps_price is flagged.

    Note: pihps_price can be legitimately updated by the koperasi after a
    confirm.  This heuristic therefore surfaces *recent* deviations (within
    the last 30 days) to limit false positives from historical price changes.
    """
    since = datetime.now(tz=timezone.utc) - timedelta(days=30)

    result = await session.execute(
        select(HarvestIntake, Commodity.pihps_price).join(
            Commodity, Commodity.id == HarvestIntake.commodity_id
        ).where(
            HarvestIntake.koperasi_id == koperasi_id,
            HarvestIntake.status == IntakeStatus.confirmed,
            HarvestIntake.price_per_kg.is_not(None),
            HarvestIntake.confirmed_at >= since,
        ).order_by(HarvestIntake.confirmed_at.desc()).limit(100)
    )
    rows = result.all()

    anomalies: list[AnomalyOut] = []
    for intake, pihps_price in rows:
        # Decimal comparison — exact equality required (CLAUDE.md: prices are PIHPS-locked)
        if intake.price_per_kg != pihps_price:
            anomalies.append(
                AnomalyOut(
                    type="pihps_price_deviation",
                    severity="high",
                    entity_type="harvest_intakes",
                    entity_id=intake.id,
                    detail=(
                        f"Harvest intake id={intake.id} confirmed with "
                        f"price_per_kg={intake.price_per_kg} but commodity "
                        f"pihps_price is currently {pihps_price}. "
                        "PIHPS prices are system-locked at confirmation — "
                        "any deviation is suspicious."
                    ),
                    created_at=intake.confirmed_at,
                )
            )
    return anomalies


# ---------------------------------------------------------------------------
# (C) Unusually large single debit entries vs koperasi median
# ---------------------------------------------------------------------------


async def _check_large_ledger_entries(
    session: AsyncSession,
    *,
    koperasi_id: int,
) -> list[AnomalyOut]:
    """
    Heuristic C: debit entries exceeding 5× the median debit amount.

    Computes the median debit amount for the koperasi using SQL percentile
    approximation (percentile_cont), then flags individual debit entries that
    exceed the threshold.  Only entries from the past 90 days are scanned to
    keep result counts manageable.

    Falls back gracefully if the koperasi has too few debit entries to compute
    a meaningful median (fewer than 5 entries → skip).
    """
    since = datetime.now(tz=timezone.utc) - timedelta(days=90)

    # Count total debit entries first to guard the percentile query.
    count_result = await session.execute(
        select(func.count(LedgerEntry.id)).where(
            LedgerEntry.koperasi_id == koperasi_id,
            LedgerEntry.direction == LedgerDirection.debit,
            LedgerEntry.created_at >= since,
        )
    )
    debit_count: int = count_result.scalar_one() or 0

    if debit_count < 5:
        # Not enough data to establish a meaningful baseline.
        return []

    # Compute median debit amount using PostgreSQL percentile_cont aggregate.
    median_result = await session.execute(
        select(
            func.percentile_cont(0.5).within_group(
                LedgerEntry.amount
            ).label("median_amount")
        ).where(
            LedgerEntry.koperasi_id == koperasi_id,
            LedgerEntry.direction == LedgerDirection.debit,
            LedgerEntry.created_at >= since,
        )
    )
    median_amount: Decimal | None = median_result.scalar_one_or_none()
    if not median_amount or median_amount <= _ZERO:
        return []

    threshold = median_amount * _LARGE_ENTRY_MULTIPLIER

    # Fetch entries that exceed the threshold.
    large_result = await session.execute(
        select(LedgerEntry).where(
            LedgerEntry.koperasi_id == koperasi_id,
            LedgerEntry.direction == LedgerDirection.debit,
            LedgerEntry.amount > threshold,
            LedgerEntry.created_at >= since,
        ).order_by(LedgerEntry.created_at.desc()).limit(20)
    )
    large_entries = large_result.scalars().all()

    anomalies: list[AnomalyOut] = []
    for entry in large_entries:
        anomalies.append(
            AnomalyOut(
                type="large_ledger_entry",
                severity="medium",
                entity_type="ledger_entries",
                entity_id=entry.id,
                detail=(
                    f"Debit ledger entry id={entry.id} amount={entry.amount} "
                    f"exceeds {_LARGE_ENTRY_MULTIPLIER}× the 90-day median "
                    f"debit ({median_amount}). Threshold: {threshold}. "
                    f"Pool: {entry.pool.value}, type: {entry.type.value}."
                ),
                created_at=entry.created_at,
            )
        )
    return anomalies


# ---------------------------------------------------------------------------
# (D) Rapid-fire confirms by the same manager
# ---------------------------------------------------------------------------


async def _check_rapid_fire_confirms(
    session: AsyncSession,
    *,
    koperasi_id: int,
) -> list[AnomalyOut]:
    """
    Heuristic D: >= 3 intake confirmations by the same manager within 5 minutes.

    Rubber-stamping without re-weighing is a known kasir fraud pattern.
    We scan confirmed intakes from the last 7 days, group by (confirmed_by,
    5-minute bucket), and flag any bucket with >= RAPID_FIRE_THRESHOLD confirms.

    Uses PostgreSQL date_trunc / interval arithmetic via SQLAlchemy text() for
    the time-bucket grouping, then processes the result set in Python to find
    windows exceeding the threshold.
    """
    since = datetime.now(tz=timezone.utc) - timedelta(days=7)

    result = await session.execute(
        select(
            HarvestIntake.confirmed_by,
            HarvestIntake.id,
            HarvestIntake.confirmed_at,
        ).where(
            HarvestIntake.koperasi_id == koperasi_id,
            HarvestIntake.status == IntakeStatus.confirmed,
            HarvestIntake.confirmed_by.is_not(None),
            HarvestIntake.confirmed_at >= since,
        ).order_by(
            HarvestIntake.confirmed_by,
            HarvestIntake.confirmed_at,
        )
    )
    rows = result.all()

    if not rows:
        return []

    # Group by confirmed_by, then slide a RAPID_FIRE_WINDOW_MINUTES window.
    from collections import defaultdict
    by_manager: dict[int, list[tuple[int, datetime]]] = defaultdict(list)
    for confirmed_by, intake_id, confirmed_at in rows:
        by_manager[confirmed_by].append((intake_id, confirmed_at))

    window = timedelta(minutes=_RAPID_FIRE_WINDOW_MINUTES)
    anomalies: list[AnomalyOut] = []
    reported_windows: set[tuple[int, datetime]] = set()

    for manager_id, events in by_manager.items():
        # Sliding window: for each event, count how many subsequent events
        # fall within RAPID_FIRE_WINDOW_MINUTES.
        for i, (intake_id, ts) in enumerate(events):
            window_events = [
                (eid, ets)
                for (eid, ets) in events[i:]
                if ets - ts <= window
            ]
            if len(window_events) >= _RAPID_FIRE_THRESHOLD:
                # Deduplicate: only report each (manager, window_start) once.
                window_key = (manager_id, ts)
                if window_key not in reported_windows:
                    reported_windows.add(window_key)
                    ids_in_window = [eid for eid, _ in window_events]
                    anomalies.append(
                        AnomalyOut(
                            type="rapid_fire_confirms",
                            severity="medium",
                            entity_type="harvest_intakes",
                            entity_id=intake_id,
                            detail=(
                                f"Manager user_id={manager_id} confirmed "
                                f"{len(window_events)} intakes within "
                                f"{_RAPID_FIRE_WINDOW_MINUTES} minutes "
                                f"(threshold: {_RAPID_FIRE_THRESHOLD}). "
                                f"Intake IDs: {ids_in_window}. "
                                "Possible rubber-stamping without re-weighing."
                            ),
                            created_at=ts,
                        )
                    )

    return anomalies


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


async def detect_anomalies(
    session: AsyncSession,
    *,
    koperasi_id: int,
) -> list[AnomalyOut]:
    """
    Run all anomaly heuristics for *koperasi_id* and return the combined results.

    Read-only — this function never writes to the database.
    All checks are tenant-scoped by koperasi_id.

    Returns a list of AnomalyOut instances sorted by created_at descending
    (most recent first).  An empty list means no anomalies were detected.

    Heuristics:
        (A) orphan_debit            — debit entries with no reference_id
        (B) pihps_price_deviation   — confirmed intakes with wrong price_per_kg
        (C) large_ledger_entry      — debit > 5× median debit (90-day window)
        (D) rapid_fire_confirms     — ≥3 confirms by same manager in 5 min
    """
    results: list[AnomalyOut] = []

    # Run each heuristic and accumulate, logging failures individually so one
    # broken check does not suppress the others.
    for checker_name, checker in [
        ("orphan_debits", _check_orphan_debits),
        ("pihps_deviations", _check_pihps_deviations),
        ("large_ledger_entries", _check_large_ledger_entries),
        ("rapid_fire_confirms", _check_rapid_fire_confirms),
    ]:
        try:
            findings = await checker(session, koperasi_id=koperasi_id)
            results.extend(findings)
        except Exception:
            logger.exception(
                "detect_anomalies: heuristic %r failed for koperasi=%d",
                checker_name,
                koperasi_id,
            )

    # Sort by created_at descending; entries with None created_at go last.
    results.sort(
        key=lambda a: a.created_at or datetime.min.replace(tzinfo=timezone.utc),
        reverse=True,
    )

    logger.info(
        "detect_anomalies: koperasi=%d found=%d anomaly/ies",
        koperasi_id,
        len(results),
    )
    return results
