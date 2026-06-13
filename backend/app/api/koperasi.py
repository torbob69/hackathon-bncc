"""
Koperasi onboarding and profile router.

Prefix  : /koperasi
Tags    : koperasi

Endpoints
---------
POST   /koperasi                  — platform_admin: create koperasi + zero-balance funds row (one txn).
GET    /koperasi                  — platform_admin: list all koperasi (cross-tenant; this role is allowed).
GET    /koperasi/me/profile       — admin | manager: own koperasi + fund balances (tenant-scoped).
GET    /koperasi/{koperasi_id}    — platform_admin: single koperasi by id.
PATCH  /koperasi/{koperasi_id}    — platform_admin: partial update + audit entry.

Multi-tenancy rules (CLAUDE.md §3.2 / §8):
  - platform_admin is intentionally cross-tenant here — it operates the platform.
  - /me/profile is tenant-scoped: id is derived from the JWT via get_tenant_id,
    never accepted as a path/query parameter.
  - KoperasiFunds is created atomically with Koperasi in POST so the row always
    exists; GET /me/profile handles the rare bootstrap gap with a get-or-create
    (same pattern as admin/funds.py).

Transaction discipline:
  - POST: session.begin() wraps koperasi + funds insert + audit — one commit.
  - PATCH: session.begin() wraps update + audit — one commit.
  - GET endpoints are read-only; no explicit begin() needed.
"""
from __future__ import annotations

import logging
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import CurrentUser, get_current_user, get_tenant_id, require_role
from app.db.engine import get_session
from app.models.enums import UserRole
from app.models.koperasi import Koperasi, KoperasiFunds
from app.schemas.koperasi import (
    KoperasiCreate,
    KoperasiFundsOut,
    KoperasiOut,
    KoperasiUpdate,
    KoperasiWithFundsOut,
)
from app.services.audit import write_audit

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/koperasi", tags=["koperasi"])

# ---------------------------------------------------------------------------
# Shared role dependencies
# ---------------------------------------------------------------------------

_platform_admin_dep = require_role(UserRole.platform_admin)
_tenant_staff_dep = require_role(UserRole.admin, UserRole.manager)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


async def _get_koperasi_or_404(session: AsyncSession, koperasi_id: int) -> Koperasi:
    """Load a Koperasi row by PK; raise HTTP 404 if not found."""
    result = await session.execute(
        select(Koperasi).where(Koperasi.id == koperasi_id)
    )
    koperasi = result.scalar_one_or_none()
    if koperasi is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Koperasi {koperasi_id} not found.",
        )
    return koperasi


async def _get_or_create_funds(session: AsyncSession, koperasi_id: int) -> KoperasiFunds:
    """
    Return the KoperasiFunds row for koperasi_id.

    If the row does not yet exist (edge case for legacy or partially-created
    tenants), bootstrap it with zero balances inside its own transaction.
    This mirrors the pattern in admin/funds.py to ensure callers always get
    a valid response.
    """
    result = await session.execute(
        select(KoperasiFunds).where(KoperasiFunds.koperasi_id == koperasi_id)
    )
    funds = result.scalar_one_or_none()

    if funds is None:
        async with session.begin():
            funds = KoperasiFunds(
                koperasi_id=koperasi_id,
                marginal_profit_pool_balance=Decimal("0"),
                loan_pool_balance=Decimal("0"),
            )
            session.add(funds)
        # Reload clean state after commit.
        result = await session.execute(
            select(KoperasiFunds).where(KoperasiFunds.koperasi_id == koperasi_id)
        )
        funds = result.scalar_one()

    return funds


# ---------------------------------------------------------------------------
# POST /koperasi  — create a new tenant koperasi
# ---------------------------------------------------------------------------


@router.post(
    "",
    response_model=KoperasiOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new koperasi tenant (platform_admin only)",
)
async def create_koperasi(
    body: KoperasiCreate,
    request: Request,
    current_user: CurrentUser = Depends(_platform_admin_dep),
    session: AsyncSession = Depends(get_session),
) -> KoperasiOut:
    """
    Onboard a new koperasi onto the platform.

    Business rules:
      - Only platform_admin may create koperasi (cross-tenant operation).
      - The KoperasiFunds row (both pools at zero) is created in the SAME
        transaction as the Koperasi row — the funds row must always exist.
      - An audit entry is written inside the same transaction.
      - Returns HTTP 201 with the created Koperasi.

    If a koperasi with the same name already exists in the same region the
    create still succeeds — uniqueness is not enforced at the name level
    (two cooperatives can share a name across regions).
    """
    ip = request.client.host if request.client else None

    async with session.begin():
        koperasi = Koperasi(
            name=body.name,
            type=body.type,
            address=body.address,
            region=body.region,
            xendit_account_id=body.xendit_account_id,
        )
        session.add(koperasi)
        # Flush to populate koperasi.id before creating funds row.
        await session.flush()

        funds = KoperasiFunds(
            koperasi_id=koperasi.id,
            marginal_profit_pool_balance=Decimal("0"),
            loan_pool_balance=Decimal("0"),
        )
        session.add(funds)
        await session.flush()

        await write_audit(
            session,
            actor_user_id=current_user.user_id,
            koperasi_id=koperasi.id,
            action="koperasi_onboarded",
            entity_type="koperasi",
            entity_id=koperasi.id,
            after={
                "name": koperasi.name,
                "type": koperasi.type,
                "region": koperasi.region,
            },
            ip=ip,
        )
        # session.begin() context manager commits here on clean exit.

    logger.info(
        "koperasi_onboarded: id=%d name=%r actor=%d",
        koperasi.id,
        koperasi.name,
        current_user.user_id,
    )

    return KoperasiOut.model_validate(koperasi)


# ---------------------------------------------------------------------------
# GET /koperasi  — list all koperasi
# ---------------------------------------------------------------------------


@router.get(
    "",
    response_model=list[KoperasiOut],
    summary="List all koperasi tenants (platform_admin only)",
)
async def list_koperasi(
    current_user: CurrentUser = Depends(_platform_admin_dep),
    session: AsyncSession = Depends(get_session),
) -> list[KoperasiOut]:
    """
    Return all koperasi rows, ordered by creation time (newest first).

    This is a cross-tenant read intentionally allowed for platform_admin;
    the RBAC guard on this endpoint blocks every other role.
    """
    result = await session.execute(
        select(Koperasi).order_by(Koperasi.created_at.desc())
    )
    rows = result.scalars().all()
    return [KoperasiOut.model_validate(row) for row in rows]


# ---------------------------------------------------------------------------
# GET /koperasi/me/profile  — tenant-scoped profile for admin / manager
#
# IMPORTANT: this route is declared BEFORE /{koperasi_id} so FastAPI
# matches the literal path segment "me" instead of treating it as an int.
# ---------------------------------------------------------------------------


@router.get(
    "/me/profile",
    response_model=KoperasiWithFundsOut,
    summary="Get own koperasi profile and fund balances (admin / manager)",
)
async def get_my_koperasi_profile(
    current_user: CurrentUser = Depends(_tenant_staff_dep),
    session: AsyncSession = Depends(get_session),
) -> KoperasiWithFundsOut:
    """
    Return the caller's own koperasi profile together with the current pool
    balances (Marginal Profit Pool + Loan Pool).

    Tenant isolation is enforced by deriving the koperasi_id from the
    authenticated user's JWT — the caller cannot request a different tenant's
    data by supplying an id parameter (no such parameter exists here).

    If the KoperasiFunds row is missing for any reason it is bootstrapped
    with zero balances so the caller always receives a valid response.
    """
    koperasi_id = get_tenant_id(current_user)

    koperasi = await _get_koperasi_or_404(session, koperasi_id)
    funds = await _get_or_create_funds(session, koperasi_id)

    return KoperasiWithFundsOut(
        koperasi=KoperasiOut.model_validate(koperasi),
        funds=KoperasiFundsOut.model_validate(funds),
    )


# ---------------------------------------------------------------------------
# GET /koperasi/{koperasi_id}  — single koperasi by PK
# ---------------------------------------------------------------------------


@router.get(
    "/{koperasi_id}",
    response_model=KoperasiOut,
    summary="Get a single koperasi by id (platform_admin only)",
)
async def get_koperasi(
    koperasi_id: int,
    current_user: CurrentUser = Depends(_platform_admin_dep),
    session: AsyncSession = Depends(get_session),
) -> KoperasiOut:
    """
    Return a single koperasi row by PK.

    Raises HTTP 404 if the koperasi does not exist.
    Only platform_admin may call this endpoint.
    """
    koperasi = await _get_koperasi_or_404(session, koperasi_id)
    return KoperasiOut.model_validate(koperasi)


# ---------------------------------------------------------------------------
# PATCH /koperasi/{koperasi_id}  — partial update
# ---------------------------------------------------------------------------


@router.patch(
    "/{koperasi_id}",
    response_model=KoperasiOut,
    summary="Partially update a koperasi (platform_admin only)",
)
async def update_koperasi(
    koperasi_id: int,
    body: KoperasiUpdate,
    request: Request,
    current_user: CurrentUser = Depends(_platform_admin_dep),
    session: AsyncSession = Depends(get_session),
) -> KoperasiOut:
    """
    Apply a partial update to an existing koperasi.

    Only the fields present and non-None in the request body are updated;
    omitted fields retain their current values.

    An audit entry capturing before/after snapshots is written in the same
    transaction as the update.

    Raises HTTP 404 if the koperasi does not exist.
    """
    ip = request.client.host if request.client else None

    async with session.begin():
        koperasi = await _get_koperasi_or_404(session, koperasi_id)

        # Capture before-state for audit trail.
        before_snapshot = {
            "name": koperasi.name,
            "type": koperasi.type,
            "address": koperasi.address,
            "region": koperasi.region,
            "xendit_account_id": koperasi.xendit_account_id,
        }

        # Apply only the fields that were explicitly provided.
        update_data = body.model_dump(exclude_none=True)
        if not update_data:
            # Nothing to update — return current state without touching DB.
            return KoperasiOut.model_validate(koperasi)

        for field, value in update_data.items():
            setattr(koperasi, field, value)

        await session.flush()

        after_snapshot = {
            "name": koperasi.name,
            "type": koperasi.type,
            "address": koperasi.address,
            "region": koperasi.region,
            "xendit_account_id": koperasi.xendit_account_id,
        }

        await write_audit(
            session,
            actor_user_id=current_user.user_id,
            koperasi_id=koperasi_id,
            action="koperasi_updated",
            entity_type="koperasi",
            entity_id=koperasi_id,
            before=before_snapshot,
            after=after_snapshot,
            ip=ip,
        )
        # session.begin() context manager commits here on clean exit.

    logger.info(
        "koperasi_updated: id=%d fields=%s actor=%d",
        koperasi_id,
        list(update_data.keys()),
        current_user.user_id,
    )

    return KoperasiOut.model_validate(koperasi)
