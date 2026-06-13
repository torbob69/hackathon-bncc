"""
Admin funds management router — pool balances + APBN grant posting.

Prefix  : /admin
Tags    : admin:funds

Endpoints
---------
GET  /admin/funds              — Current pool balances for the caller's koperasi.
POST /admin/funds/apbn-grant   — Credit the Loan Pool with an APBN government grant.
GET  /admin/ledger             — Tenant-scoped ledger history with optional filters.

All endpoints require role=admin (enforced via Depends(require_role(UserRole.admin))).
Every query is scoped by koperasi_id (CLAUDE.md §3.2 / §8 — never unscoped).

Pool rules enforced here (CLAUDE.md §2.4):
  - APBN grant → Loan Pool only  (credit_loan_pool convenience wrapper).
  - Post-grant the Marginal Profit Pool is NEVER touched.
  - InsufficientFunds shouldn't occur for a credit but is mapped to 422 defensively.
  - PoolInvariantViolation is mapped to 422 with a clear detail.

Transaction discipline:
  - The APBN flow (credit + audit) runs in a single session.begin() block.
  - We never commit inside a service helper; the route owns the commit.
"""
from __future__ import annotations

import logging
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import CurrentUser, get_tenant_id, require_role
from app.db.engine import get_session
from app.models.enums import LedgerPool, LedgerType, UserRole
from app.models.koperasi import KoperasiFunds
from app.models.ledger import LedgerEntry
from app.schemas.funds import (
    ApbnGrantRequest,
    ApbnGrantResponse,
    FundsOut,
    LedgerEntryOut,
)
from app.services.audit import write_audit
from app.services.ledger import (
    InsufficientFunds,
    PoolInvariantViolation,
    credit_loan_pool,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["admin:funds"])

# ---------------------------------------------------------------------------
# Shared admin dependency
# ---------------------------------------------------------------------------

_admin_dep = require_role(UserRole.admin)


# ---------------------------------------------------------------------------
# GET /admin/funds
# ---------------------------------------------------------------------------


@router.get(
    "/funds",
    response_model=FundsOut,
    summary="Get current pool balances for the caller's koperasi",
)
async def get_funds(
    current_user: CurrentUser = Depends(_admin_dep),
    session: AsyncSession = Depends(get_session),
) -> FundsOut:
    """
    Return the KoperasiFunds row for the authenticated admin's koperasi.

    If the row does not yet exist (new koperasi) it is created with zero
    balances so the admin always gets a valid response.

    Tenant-scoped — never returns another koperasi's funds.
    """
    koperasi_id = get_tenant_id(current_user)

    result = await session.execute(
        select(KoperasiFunds).where(KoperasiFunds.koperasi_id == koperasi_id)
    )
    funds = result.scalar_one_or_none()

    if funds is None:
        # Bootstrap a zero-balance row; commit so it persists.
        async with session.begin():
            funds = KoperasiFunds(
                koperasi_id=koperasi_id,
                marginal_profit_pool_balance=Decimal("0"),
                loan_pool_balance=Decimal("0"),
            )
            session.add(funds)
        # Reload after commit so ORM state is clean.
        result = await session.execute(
            select(KoperasiFunds).where(KoperasiFunds.koperasi_id == koperasi_id)
        )
        funds = result.scalar_one()

    return FundsOut.model_validate(funds)


# ---------------------------------------------------------------------------
# POST /admin/funds/apbn-grant
# ---------------------------------------------------------------------------


@router.post(
    "/funds/apbn-grant",
    response_model=ApbnGrantResponse,
    status_code=status.HTTP_200_OK,
    summary="Credit the Loan Pool with an APBN government grant",
)
async def post_apbn_grant(
    body: ApbnGrantRequest,
    request: Request,
    current_user: CurrentUser = Depends(_admin_dep),
    session: AsyncSession = Depends(get_session),
) -> ApbnGrantResponse:
    """
    Post an APBN (government grant) credit to the Loan Pool.

    Business rules enforced (CLAUDE.md §2.4 / §8):
      - Funds go to the Loan Pool ONLY — the pool invariant (chk_pool_type
        CHECK + Python layer) blocks any accidental cross-pool write.
      - The Marginal Profit Pool is never touched.
      - If *idempotency_key* was used before, the existing ledger entry is
        returned as-is — no double-posting.
      - The ledger write and audit entry land in ONE transaction.

    Returns the ledger entry and the updated fund balances.
    """
    koperasi_id = get_tenant_id(current_user)
    amount = Decimal(str(body.amount))
    ip = request.client.host if request.client else None

    try:
        async with session.begin():
            # Credit Loan Pool — SELECT FOR UPDATE koperasi_funds is inside
            # credit_loan_pool → post_ledger_entry (CLAUDE.md §8 locking rule).
            entry = await credit_loan_pool(
                session,
                koperasi_id=koperasi_id,
                amount=amount,
                reference_type="apbn_grant",
                external_idempotency_key=body.idempotency_key,
            )

            # Audit trail — same transaction as the ledger write.
            await write_audit(
                session,
                actor_user_id=current_user.user_id,
                koperasi_id=koperasi_id,
                action="apbn_grant",
                entity_type="koperasi_funds",
                entity_id=koperasi_id,
                after={
                    "amount": str(amount),
                    "note": body.note,
                    "idempotency_key": body.idempotency_key,
                    "ledger_entry_id": entry.id,
                },
                ip=ip,
            )
            # session.begin() context manager commits here on clean exit.

    except PoolInvariantViolation as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Pool invariant violation: {exc}",
        ) from exc
    except InsufficientFunds as exc:
        # Should never happen for a credit, but mapped defensively.
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Insufficient funds in {exc.pool.value} pool: "
                f"available={exc.available}, requested={exc.requested}"
            ),
        ) from exc

    # Re-read current funds (post-commit, clean state).
    funds_result = await session.execute(
        select(KoperasiFunds).where(KoperasiFunds.koperasi_id == koperasi_id)
    )
    funds = funds_result.scalar_one()

    logger.info(
        "apbn_grant: koperasi=%d amount=%s entry_id=%d actor=%d",
        koperasi_id,
        amount,
        entry.id,
        current_user.user_id,
    )

    return ApbnGrantResponse(
        ledger_entry=LedgerEntryOut.model_validate(entry),
        funds=FundsOut.model_validate(funds),
    )


# ---------------------------------------------------------------------------
# POST /admin/funds/marginal-dummy
# ---------------------------------------------------------------------------


@router.post(
    "/funds/marginal-dummy",
    response_model=ApbnGrantResponse,
    status_code=status.HTTP_200_OK,
    summary="Dummy top up for Marginal Profit Pool (Testing only)",
)
async def post_marginal_dummy(
    body: ApbnGrantRequest,
    request: Request,
    current_user: CurrentUser = Depends(_admin_dep),
    session: AsyncSession = Depends(get_session),
) -> ApbnGrantResponse:
    """
    Simulate profit injection to the Marginal Profit Pool for Hackathon demo/testing.
    Uses LedgerType.refund to bypass the APBN constraint.
    """
    from app.services.ledger import post_ledger_entry
    from app.models.enums import LedgerDirection

    koperasi_id = get_tenant_id(current_user)
    amount = Decimal(str(body.amount))
    ip = request.client.host if request.client else None

    try:
        async with session.begin():
            entry = await post_ledger_entry(
                session,
                koperasi_id=koperasi_id,
                pool=LedgerPool.marginal_profit,
                type=LedgerType.refund,
                amount=amount,
                direction=LedgerDirection.credit,
                reference_type="dummy_marginal_injection",
                reference_id=None,
                external_idempotency_key=body.idempotency_key,
            )

            await write_audit(
                session,
                actor_user_id=current_user.user_id,
                koperasi_id=koperasi_id,
                action="dummy_marginal_injection",
                entity_type="koperasi_funds",
                entity_id=koperasi_id,
                after={
                    "amount": str(amount),
                    "note": body.note,
                    "idempotency_key": body.idempotency_key,
                    "ledger_entry_id": entry.id,
                },
                ip=ip,
            )

    except PoolInvariantViolation as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Pool invariant violation: {exc}",
        ) from exc
    except InsufficientFunds as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    funds_result = await session.execute(
        select(KoperasiFunds).where(KoperasiFunds.koperasi_id == koperasi_id)
    )
    funds = funds_result.scalar_one()

    return ApbnGrantResponse(
        ledger_entry=LedgerEntryOut.model_validate(entry),
        funds=FundsOut.model_validate(funds),
    )


# ---------------------------------------------------------------------------
# GET /admin/ledger
# ---------------------------------------------------------------------------


@router.get(
    "/ledger",
    response_model=list[LedgerEntryOut],
    summary="Tenant-scoped ledger history with optional pool/type filters",
)
async def list_ledger(
    pool: LedgerPool | None = None,
    type: LedgerType | None = None,  # noqa: A002
    limit: int = 50,
    offset: int = 0,
    current_user: CurrentUser = Depends(_admin_dep),
    session: AsyncSession = Depends(get_session),
) -> list[LedgerEntryOut]:
    """
    Return ledger entries for the caller's koperasi, newest first.

    Query parameters:
      - pool   — filter by LedgerPool (marginal_profit | loan)
      - type   — filter by LedgerType (sale_settlement | farmer_payment | …)
      - limit  — max rows returned (1–200, default 50)
      - offset — pagination offset (default 0)

    Always filters by koperasi_id — never returns cross-tenant entries.
    """
    koperasi_id = get_tenant_id(current_user)

    # Clamp limit to prevent abuse.
    if limit < 1 or limit > 200:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="limit must be between 1 and 200.",
        )
    if offset < 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="offset must be >= 0.",
        )

    query = (
        select(LedgerEntry)
        .where(LedgerEntry.koperasi_id == koperasi_id)
        .order_by(LedgerEntry.created_at.desc())
        .limit(limit)
        .offset(offset)
    )

    if pool is not None:
        query = query.where(LedgerEntry.pool == pool)
    if type is not None:
        query = query.where(LedgerEntry.type == type)

    result = await session.execute(query)
    entries = result.scalars().all()

    return [LedgerEntryOut.model_validate(e) for e in entries]
