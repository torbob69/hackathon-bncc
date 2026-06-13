"""
Business logic for the Commodities & Catalog feature (Phase 7).

Design rules (CLAUDE.md §8):
  - Every query is scoped by koperasi_id — no cross-tenant data leaks.
  - current_stock_kg is a cached column driven by stock_movements; it is
    NEVER written from user input (only stock movement writes may touch it).
  - All mutations call write_audit() before the caller's transaction commits.
  - write_audit() does NOT commit — the caller (router) owns the transaction.
  - Exceptions CommodityNotFound and CommodityInUse are raised for the router
    to map to HTTP 404 and HTTP 409 respectively.

Functions:
  list_commodities(session, koperasi_id)
  get_commodity(session, koperasi_id, commodity_id)   — raises CommodityNotFound
  create_commodity(session, koperasi_id, actor_user_id, data)
  update_commodity(session, koperasi_id, commodity_id, actor_user_id, data)
  delete_commodity(session, koperasi_id, commodity_id, actor_user_id)
"""
from __future__ import annotations

import logging
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.commodities import Commodity
from app.models.intakes import HarvestIntake, StockMovement
from app.models.orders import OrderItem
from app.schemas.commodities import CommodityCreate, CommodityUpdate
from app.services.audit import write_audit

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Domain exceptions (router maps these to HTTP status codes)
# ---------------------------------------------------------------------------


class CommodityNotFound(Exception):
    """Raised when a commodity does not exist in the caller's koperasi."""


class CommodityInUse(Exception):
    """
    Raised when deleting a commodity that is still referenced by at least one
    stock_movement, order_item, or harvest_intake row.
    """


# ---------------------------------------------------------------------------
# Read helpers
# ---------------------------------------------------------------------------


async def list_commodities(
    session: AsyncSession,
    koperasi_id: int,
) -> list[Commodity]:
    """
    Return all commodities belonging to *koperasi_id*, ordered by name.

    Always tenant-scoped; never returns commodities from another koperasi.
    """
    stmt = (
        select(Commodity)
        .where(Commodity.koperasi_id == koperasi_id)
        .order_by(Commodity.name)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_commodity(
    session: AsyncSession,
    koperasi_id: int,
    commodity_id: int,
) -> Commodity:
    """
    Fetch a single commodity, scoped to *koperasi_id*.

    Raises:
        CommodityNotFound — if the commodity does not exist or belongs to a
                            different koperasi.
    """
    stmt = select(Commodity).where(
        Commodity.id == commodity_id,
        Commodity.koperasi_id == koperasi_id,
    )
    result = await session.execute(stmt)
    commodity = result.scalar_one_or_none()
    if commodity is None:
        raise CommodityNotFound(
            f"Commodity {commodity_id} not found in this koperasi."
        )
    return commodity


# ---------------------------------------------------------------------------
# Write helpers
# ---------------------------------------------------------------------------


async def create_commodity(
    session: AsyncSession,
    koperasi_id: int,
    actor_user_id: int,
    data: CommodityCreate,
) -> Commodity:
    """
    Create a new commodity in the caller's koperasi catalog.

    - current_stock_kg starts at 0 (server default); never set from input.
    - Writes an audit entry (action='commodity_created').
    - Does NOT commit — the router owns the transaction.

    Returns the newly created (flushed) Commodity ORM instance.
    """
    commodity = Commodity(
        koperasi_id=koperasi_id,
        name=data.name,
        unit=data.unit,
        pihps_price=data.pihps_price,
        # current_stock_kg intentionally omitted — DB server_default=0
        cold_storage_location=data.cold_storage_location,
    )
    session.add(commodity)
    await session.flush()  # populate commodity.id

    await write_audit(
        session,
        actor_user_id=actor_user_id,
        koperasi_id=koperasi_id,
        action="commodity_created",
        entity_type="commodity",
        entity_id=commodity.id,
        after={
            "name": commodity.name,
            "unit": commodity.unit,
            "pihps_price": commodity.pihps_price,
            "cold_storage_location": commodity.cold_storage_location,
        },
    )

    logger.info(
        "commodity created: id=%s koperasi_id=%s name=%r by user=%s",
        commodity.id,
        koperasi_id,
        commodity.name,
        actor_user_id,
    )
    return commodity


async def update_commodity(
    session: AsyncSession,
    koperasi_id: int,
    commodity_id: int,
    actor_user_id: int,
    data: CommodityUpdate,
) -> Commodity:
    """
    Apply a partial update to an existing commodity.

    - current_stock_kg is NEVER modified here (stock-movement-driven).
    - Only fields supplied in *data* (non-None) are applied.
    - Writes an audit entry (action='commodity_updated') with before/after snapshot.
    - Does NOT commit — the router owns the transaction.

    Raises:
        CommodityNotFound — commodity does not exist in this koperasi.
    """
    commodity = await get_commodity(session, koperasi_id, commodity_id)

    before = {
        "name": commodity.name,
        "pihps_price": commodity.pihps_price,
        "cold_storage_location": commodity.cold_storage_location,
    }

    if data.name is not None:
        commodity.name = data.name
    if data.pihps_price is not None:
        commodity.pihps_price = data.pihps_price
    if data.cold_storage_location is not None:
        commodity.cold_storage_location = data.cold_storage_location

    after = {
        "name": commodity.name,
        "pihps_price": commodity.pihps_price,
        "cold_storage_location": commodity.cold_storage_location,
    }

    session.add(commodity)
    await session.flush()

    await write_audit(
        session,
        actor_user_id=actor_user_id,
        koperasi_id=koperasi_id,
        action="commodity_updated",
        entity_type="commodity",
        entity_id=commodity.id,
        before=before,
        after=after,
    )

    logger.info(
        "commodity updated: id=%s koperasi_id=%s by user=%s",
        commodity.id,
        koperasi_id,
        actor_user_id,
    )
    return commodity


async def delete_commodity(
    session: AsyncSession,
    koperasi_id: int,
    commodity_id: int,
    actor_user_id: int,
) -> None:
    """
    Delete a commodity from the catalog.

    Guard: the commodity may NOT be deleted if any of the following tables
    reference it (referential-integrity / business-integrity check):
      - stock_movements.commodity_id
      - order_items.commodity_id
      - harvest_intakes.commodity_id

    If any reference exists, raises CommodityInUse (→ HTTP 409).

    Writes an audit entry (action='commodity_deleted') before deletion.
    Does NOT commit — the router owns the transaction.

    Raises:
        CommodityNotFound — commodity does not exist in this koperasi.
        CommodityInUse    — at least one referencing row exists.
    """
    commodity = await get_commodity(session, koperasi_id, commodity_id)

    # --- Reference guard: stock_movements ---
    sm_count_result = await session.execute(
        select(func.count()).where(
            StockMovement.commodity_id == commodity_id,
            StockMovement.koperasi_id == koperasi_id,
        )
    )
    if sm_count_result.scalar_one() > 0:
        raise CommodityInUse(
            f"Commodity {commodity_id} cannot be deleted: "
            "it is referenced by existing stock movements."
        )

    # --- Reference guard: order_items ---
    oi_count_result = await session.execute(
        select(func.count()).where(
            OrderItem.commodity_id == commodity_id,
            OrderItem.koperasi_id == koperasi_id,
        )
    )
    if oi_count_result.scalar_one() > 0:
        raise CommodityInUse(
            f"Commodity {commodity_id} cannot be deleted: "
            "it is referenced by existing order items."
        )

    # --- Reference guard: harvest_intakes ---
    hi_count_result = await session.execute(
        select(func.count()).where(
            HarvestIntake.commodity_id == commodity_id,
            HarvestIntake.koperasi_id == koperasi_id,
        )
    )
    if hi_count_result.scalar_one() > 0:
        raise CommodityInUse(
            f"Commodity {commodity_id} cannot be deleted: "
            "it is referenced by existing harvest intakes."
        )

    # --- Audit before deletion (entity will be gone after commit) ---
    await write_audit(
        session,
        actor_user_id=actor_user_id,
        koperasi_id=koperasi_id,
        action="commodity_deleted",
        entity_type="commodity",
        entity_id=commodity.id,
        before={
            "name": commodity.name,
            "unit": commodity.unit,
            "pihps_price": commodity.pihps_price,
            "current_stock_kg": commodity.current_stock_kg,
            "cold_storage_location": commodity.cold_storage_location,
        },
    )

    await session.delete(commodity)
    await session.flush()

    logger.info(
        "commodity deleted: id=%s koperasi_id=%s name=%r by user=%s",
        commodity_id,
        koperasi_id,
        commodity.name,
        actor_user_id,
    )
