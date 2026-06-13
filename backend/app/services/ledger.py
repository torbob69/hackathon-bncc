"""
Pool-safe ledger writer — the single point of entry for ALL money movements.

Critical invariants enforced here (from CLAUDE.md §3.2, §4, §8):

1. Pool ↔ Type invariant (mirrors chk_pool_type CHECK constraint):
   - loan pool          ← apbn_grant | loan_disbursement | loan_repayment
   - marginal_profit    ← sale_settlement | farmer_payment | platform_fee | refund
   Enforced in Python before touching the DB so we get a clean error, not a
   Postgres CHECK violation.

2. Concurrency / overdraft prevention:
   SELECT ... FOR UPDATE the koperasi_funds row before any balance computation.
   This serialises concurrent debits per koperasi and prevents overdraft.

3. Idempotency:
   If external_idempotency_key is provided, check for an existing LedgerEntry
   first.  Return the existing row without a second INSERT (replay-safe).

4. No commits inside this module:
   The caller owns the transaction (begin / commit / rollback).
   We only flush so that returned objects have their PKs populated.

5. balance_after is a display snapshot only — never the source of truth.

Usage:
    from decimal import Decimal
    from app.services.ledger import post_ledger_entry, InsufficientFunds

    async with session.begin():
        entry = await post_ledger_entry(
            session,
            koperasi_id=kop_id,
            pool=LedgerPool.loan,
            type=LedgerType.apbn_grant,
            amount=Decimal("5000000.00"),
            direction=LedgerDirection.credit,
            reference_type="apbn_grant_request",
            reference_id=grant_id,
            external_idempotency_key=f"apbn-{grant_id}",
        )
"""
from __future__ import annotations

import logging
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import LedgerDirection, LedgerPool, LedgerType
from app.models.koperasi import KoperasiFunds
from app.models.ledger import LedgerEntry

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Custom exceptions (exported — callers map these to HTTP status codes)
# ---------------------------------------------------------------------------


class InsufficientFunds(Exception):
    """
    Raised when a debit would push a pool balance below zero.

    Attributes:
        pool          — Which pool was underfunded.
        available     — Current available balance.
        requested     — Amount that was requested.
    """

    def __init__(self, pool: LedgerPool, available: Decimal, requested: Decimal) -> None:
        self.pool = pool
        self.available = available
        self.requested = requested
        super().__init__(
            f"Insufficient funds in {pool.value} pool: "
            f"available={available}, requested={requested}"
        )


class PoolInvariantViolation(ValueError):
    """
    Raised when the (pool, type) combination violates the business invariant.

    Callers should translate this to HTTP 422.
    """


# ---------------------------------------------------------------------------
# Pool ↔ Type invariant map
# ---------------------------------------------------------------------------

_LOAN_POOL_TYPES: frozenset[LedgerType] = frozenset(
    {LedgerType.apbn_grant, LedgerType.loan_disbursement, LedgerType.loan_repayment}
)

_MARGINAL_PROFIT_TYPES: frozenset[LedgerType] = frozenset(
    {
        LedgerType.sale_settlement,
        LedgerType.farmer_payment,
        LedgerType.platform_fee,
        LedgerType.refund,
    }
)

_POOL_ALLOWED_TYPES: dict[LedgerPool, frozenset[LedgerType]] = {
    LedgerPool.loan: _LOAN_POOL_TYPES,
    LedgerPool.marginal_profit: _MARGINAL_PROFIT_TYPES,
}


def _assert_pool_invariant(pool: LedgerPool, ledger_type: LedgerType) -> None:
    """Raise PoolInvariantViolation if (pool, type) is not permitted."""
    allowed = _POOL_ALLOWED_TYPES.get(pool, frozenset())
    if ledger_type not in allowed:
        raise PoolInvariantViolation(
            f"LedgerType.{ledger_type.value} is not allowed in pool={pool.value}. "
            f"Allowed types for this pool: {[t.value for t in allowed]}"
        )


# ---------------------------------------------------------------------------
# KoperasiFunds get-or-create helper (FOR UPDATE safe)
# ---------------------------------------------------------------------------


async def _get_or_create_funds_for_update(
    session: AsyncSession, koperasi_id: int
) -> KoperasiFunds:
    """
    Fetch the KoperasiFunds row for *koperasi_id* with a row-level lock
    (SELECT ... FOR UPDATE).

    If the row does not exist yet, insert a zero-balance row first, then
    re-select with FOR UPDATE.  This avoids the lost-update race that would
    occur if we just inserted without locking.

    Must be called inside an open transaction.
    """
    result = await session.execute(
        select(KoperasiFunds)
        .where(KoperasiFunds.koperasi_id == koperasi_id)
        .with_for_update()
    )
    funds = result.scalar_one_or_none()

    if funds is None:
        # Row doesn't exist yet — create zero-balance row, then lock it.
        funds = KoperasiFunds(
            koperasi_id=koperasi_id,
            marginal_profit_pool_balance=Decimal("0"),
            loan_pool_balance=Decimal("0"),
            updated_at=datetime.now(UTC),
        )
        session.add(funds)
        await session.flush()  # write the row so we can lock it

        # Re-acquire with FOR UPDATE now that the row exists.
        result2 = await session.execute(
            select(KoperasiFunds)
            .where(KoperasiFunds.koperasi_id == koperasi_id)
            .with_for_update()
        )
        funds = result2.scalar_one()  # must exist now

    return funds


# ---------------------------------------------------------------------------
# Core ledger writer
# ---------------------------------------------------------------------------


async def post_ledger_entry(
    session: AsyncSession,
    *,
    koperasi_id: int,
    pool: LedgerPool,
    type: LedgerType,  # noqa: A002  (shadows builtin — kept for domain clarity)
    amount: Decimal,
    direction: LedgerDirection,
    reference_type: str | None = None,
    reference_id: int | None = None,
    external_idempotency_key: str | None = None,
    xendit_disbursement_id: str | None = None,
) -> LedgerEntry:
    """
    Record one money movement against the correct pool with concurrency safety.

    Steps (all within the CALLER's transaction — we never commit):
      a. Idempotency check — if external_idempotency_key already exists,
         return the existing entry without a second INSERT.
      b. Pool ↔ Type invariant check (Python mirror of chk_pool_type).
      c. SELECT ... FOR UPDATE the koperasi_funds row (get-or-create if missing).
      d. Compute new balance (credit adds, debit subtracts).
      e. Debit guard — raise InsufficientFunds if new balance would be < 0.
      f. Update koperasi_funds balance + updated_at.
      g. INSERT LedgerEntry with balance_after snapshot. Flush.

    Parameters:
        session                   — Active AsyncSession; caller owns begin/commit.
        koperasi_id               — Tenant scope.
        pool                      — LedgerPool.loan or LedgerPool.marginal_profit.
        type                      — LedgerType value.
        amount                    — Positive Decimal amount.  Never float.
        direction                 — LedgerDirection.credit or .debit.
        reference_type            — Optional domain table name (e.g. "loans").
        reference_id              — Optional PK of the referenced row.
        external_idempotency_key  — If provided, the entry will only be inserted
                                    once.  Replays return the existing entry.
        xendit_disbursement_id    — Xendit disbursement ID for payout entries.

    Returns:
        The flushed (but not committed) LedgerEntry ORM instance.

    Raises:
        InsufficientFunds         — Debit would push the pool balance below 0.
        PoolInvariantViolation    — (pool, type) combination is forbidden.
    """
    # Ensure amount is Decimal (guard against accidental float callers)
    amount = Decimal(str(amount))

    # --- a. Idempotency check ---
    if external_idempotency_key is not None:
        existing_result = await session.execute(
            select(LedgerEntry).where(
                LedgerEntry.external_idempotency_key == external_idempotency_key
            )
        )
        existing = existing_result.scalar_one_or_none()
        if existing is not None:
            logger.info(
                "ledger: idempotent replay for key=%s — returning existing entry id=%d",
                external_idempotency_key,
                existing.id,
            )
            return existing

    # --- b. Pool invariant ---
    _assert_pool_invariant(pool, type)

    # --- c. Lock koperasi_funds row ---
    funds = await _get_or_create_funds_for_update(session, koperasi_id)

    # --- d. Compute new balance ---
    if pool == LedgerPool.loan:
        current_balance: Decimal = Decimal(str(funds.loan_pool_balance))
    else:  # marginal_profit
        current_balance = Decimal(str(funds.marginal_profit_pool_balance))

    if direction == LedgerDirection.credit:
        new_balance = current_balance + amount
    else:  # debit
        new_balance = current_balance - amount

    # --- e. Debit guard ---
    if direction == LedgerDirection.debit and new_balance < Decimal("0"):
        raise InsufficientFunds(pool=pool, available=current_balance, requested=amount)

    # --- f. Update funds ---
    if pool == LedgerPool.loan:
        funds.loan_pool_balance = new_balance
    else:
        funds.marginal_profit_pool_balance = new_balance
    funds.updated_at = datetime.now(UTC)

    # --- g. Insert ledger entry ---
    entry = LedgerEntry(
        koperasi_id=koperasi_id,
        pool=pool,
        type=type,
        amount=amount,
        direction=direction,
        reference_type=reference_type,
        reference_id=reference_id,
        external_idempotency_key=external_idempotency_key,
        xendit_disbursement_id=xendit_disbursement_id,
        balance_after=new_balance,  # display snapshot only
    )
    session.add(entry)
    await session.flush()  # populate entry.id without committing

    logger.info(
        "ledger: koperasi=%d pool=%s type=%s direction=%s amount=%s "
        "prev_balance=%s new_balance=%s entry_id=%d",
        koperasi_id,
        pool.value,
        type.value,
        direction.value,
        amount,
        current_balance,
        new_balance,
        entry.id,
    )
    return entry


# ---------------------------------------------------------------------------
# Convenience wrappers
# ---------------------------------------------------------------------------


async def credit_loan_pool(
    session: AsyncSession,
    *,
    koperasi_id: int,
    amount: Decimal,
    reference_type: str | None = None,
    reference_id: int | None = None,
    external_idempotency_key: str | None = None,
) -> LedgerEntry:
    """
    Convenience wrapper: credit the Loan Pool with an APBN grant.

    This is the ONLY permitted way to fund the Loan Pool — government grants
    (APBN).  The pool invariant ensures no trading margin can enter.
    """
    return await post_ledger_entry(
        session,
        koperasi_id=koperasi_id,
        pool=LedgerPool.loan,
        type=LedgerType.apbn_grant,
        amount=amount,
        direction=LedgerDirection.credit,
        reference_type=reference_type,
        reference_id=reference_id,
        external_idempotency_key=external_idempotency_key,
    )


async def debit_loan_pool(
    session: AsyncSession,
    *,
    koperasi_id: int,
    ledger_type: LedgerType,
    amount: Decimal,
    reference_type: str | None = None,
    reference_id: int | None = None,
    external_idempotency_key: str | None = None,
    xendit_disbursement_id: str | None = None,
) -> LedgerEntry:
    """
    Convenience wrapper: debit the Loan Pool (disbursement or repayment credit).

    ledger_type must be LedgerType.loan_disbursement or LedgerType.loan_repayment.
    """
    return await post_ledger_entry(
        session,
        koperasi_id=koperasi_id,
        pool=LedgerPool.loan,
        type=ledger_type,
        amount=amount,
        direction=LedgerDirection.debit,
        reference_type=reference_type,
        reference_id=reference_id,
        external_idempotency_key=external_idempotency_key,
        xendit_disbursement_id=xendit_disbursement_id,
    )
