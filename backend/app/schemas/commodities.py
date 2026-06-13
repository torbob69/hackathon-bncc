"""
Pydantic v2 schemas for the Commodities & Catalog feature (Phase 7).

CommodityCreate  — input for POST /commodities
CommodityUpdate  — input for PATCH /commodities/{id}  (all fields optional)
CommodityOut     — response shape for all commodity endpoints

Money convention: pihps_price is Decimal (Numeric(18,2) in the DB).
Weight convention: current_stock_kg is Decimal (Numeric(10,3)) — READ-ONLY;
  it is driven by stock_movements and must never be accepted from user input.
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class CommodityCreate(BaseModel):
    """
    Payload for creating a new commodity in the caller's koperasi catalog.

    Fields:
        name                  — commodity name (e.g. "Bayam", "Kangkung").
        pihps_price           — PIHPS reference price per kg (Decimal > 0).
        unit                  — unit of measure; defaults to 'kg' per spec.
        cold_storage_location — optional location label for cold-storage tracking.
    """

    name: str = Field(..., min_length=1, max_length=255, description="Commodity name")
    pihps_price: Decimal = Field(
        ...,
        gt=0,
        description="PIHPS reference price per kg (must be positive)",
    )
    unit: str = Field(
        default="kg",
        max_length=10,
        description="Unit of measure (default: kg)",
    )
    cold_storage_location: str | None = Field(
        default=None,
        max_length=255,
        description="Optional cold-storage location label",
    )


class CommodityUpdate(BaseModel):
    """
    Payload for PATCH /commodities/{id}.

    All fields are optional — only supplied fields are applied.
    current_stock_kg is intentionally absent: it is stock-movement-driven
    and must never be set from a client request.
    """

    name: str | None = Field(default=None, min_length=1, max_length=255)
    pihps_price: Decimal | None = Field(default=None, gt=0)
    cold_storage_location: str | None = Field(default=None, max_length=255)


class CommodityOut(BaseModel):
    """
    Commodity record returned by all catalog endpoints.

    current_stock_kg is included for display purposes but is a server-managed
    cache — callers must not attempt to SET it via CommodityUpdate.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    koperasi_id: int
    name: str
    unit: str
    pihps_price: Decimal
    current_stock_kg: Decimal
    cold_storage_location: str | None
    created_at: datetime
