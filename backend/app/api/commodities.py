"""
Commodities & Catalog API — Phase 7.

Router prefix : /commodities
Tags          : ["commodities"]
Auth          : every endpoint requires UserRole.manager OR UserRole.admin
Tenant        : resolved from JWT via get_tenant_id(current_user)

Endpoints:
  POST   /commodities                   — create a commodity (201)
  GET    /commodities                   — list all commodities in the koperasi
  GET    /commodities/{commodity_id}    — fetch a single commodity
  PATCH  /commodities/{commodity_id}    — partial update (never touches current_stock_kg)
  DELETE /commodities/{commodity_id}    — delete if not referenced (204)

Business logic lives in app.services.commodities; this is a thin HTTP layer.

Note: the distributor-facing marketplace catalog browse lives in
services/orders.py (list_catalog) and is NOT duplicated here.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import CurrentUser, get_tenant_id, require_role
from app.db.engine import get_session
from app.models.enums import UserRole
from app.schemas.commodities import CommodityCreate, CommodityOut, CommodityUpdate
from app.services.commodities import (
    CommodityInUse,
    CommodityNotFound,
    create_commodity,
    delete_commodity,
    get_commodity,
    list_commodities,
    update_commodity,
)

router = APIRouter(prefix="/commodities", tags=["commodities"])

# Reusable role guard — manager or admin can manage the catalog.
_mgr_admin = Depends(require_role(UserRole.manager, UserRole.admin))


# ---------------------------------------------------------------------------
# POST /commodities
# ---------------------------------------------------------------------------


@router.post("", response_model=CommodityOut, status_code=status.HTTP_201_CREATED)
async def create_one_commodity(
    body: CommodityCreate,
    current_user: CurrentUser = _mgr_admin,
    session: AsyncSession = Depends(get_session),
) -> CommodityOut:
    """
    Create a new commodity in the caller's koperasi catalog.

    - `current_stock_kg` is always initialised to 0 by the server;
      it is NOT accepted from this request body.
    - `pihps_price` must be a positive Decimal (PIHPS reference price per kg).
    """
    koperasi_id = get_tenant_id(current_user)
    async with session.begin():
        commodity = await create_commodity(
            session,
            koperasi_id=koperasi_id,
            actor_user_id=current_user.user_id,
            data=body,
        )
    return CommodityOut.model_validate(commodity)


# ---------------------------------------------------------------------------
# GET /commodities
# ---------------------------------------------------------------------------


@router.get("", response_model=list[CommodityOut])
async def list_catalog(
    current_user: CurrentUser = _mgr_admin,
    session: AsyncSession = Depends(get_session),
) -> list[CommodityOut]:
    """
    List all commodities in the caller's koperasi, ordered by name.

    Always tenant-scoped — no other koperasi's commodities are returned.
    """
    koperasi_id = get_tenant_id(current_user)
    rows = await list_commodities(session, koperasi_id=koperasi_id)
    return [CommodityOut.model_validate(row) for row in rows]


# ---------------------------------------------------------------------------
# GET /commodities/{commodity_id}
# ---------------------------------------------------------------------------


@router.get("/{commodity_id}", response_model=CommodityOut)
async def get_one_commodity(
    commodity_id: int,
    current_user: CurrentUser = _mgr_admin,
    session: AsyncSession = Depends(get_session),
) -> CommodityOut:
    """Return a single commodity, scoped to the caller's koperasi."""
    koperasi_id = get_tenant_id(current_user)
    try:
        commodity = await get_commodity(session, koperasi_id=koperasi_id, commodity_id=commodity_id)
    except CommodityNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return CommodityOut.model_validate(commodity)


# ---------------------------------------------------------------------------
# PATCH /commodities/{commodity_id}
# ---------------------------------------------------------------------------


@router.patch("/{commodity_id}", response_model=CommodityOut)
async def update_one_commodity(
    commodity_id: int,
    body: CommodityUpdate,
    current_user: CurrentUser = _mgr_admin,
    session: AsyncSession = Depends(get_session),
) -> CommodityOut:
    """
    Partially update a commodity.

    - Only supplied (non-null) fields are applied.
    - `current_stock_kg` is never modified by this endpoint; it remains
      stock-movement-driven.
    """
    koperasi_id = get_tenant_id(current_user)
    async with session.begin():
        try:
            commodity = await update_commodity(
                session,
                koperasi_id=koperasi_id,
                commodity_id=commodity_id,
                actor_user_id=current_user.user_id,
                data=body,
            )
        except CommodityNotFound as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return CommodityOut.model_validate(commodity)


# ---------------------------------------------------------------------------
# DELETE /commodities/{commodity_id}
# ---------------------------------------------------------------------------


@router.delete("/{commodity_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_one_commodity(
    commodity_id: int,
    current_user: CurrentUser = _mgr_admin,
    session: AsyncSession = Depends(get_session),
) -> None:
    """
    Delete a commodity from the catalog.

    Blocked (HTTP 409) if the commodity is referenced by any existing
    stock movement, order item, or harvest intake — deletion would break
    referential integrity and historical records.
    """
    koperasi_id = get_tenant_id(current_user)
    async with session.begin():
        try:
            await delete_commodity(
                session,
                koperasi_id=koperasi_id,
                commodity_id=commodity_id,
                actor_user_id=current_user.user_id,
            )
        except CommodityNotFound as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
        except CommodityInUse as exc:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
