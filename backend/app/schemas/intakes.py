from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import IntakeStatus


class IntakeCreateRequest(BaseModel):
    commodity_id: int
    weight_kg: Decimal = Field(..., gt=0, decimal_places=3)


class IntakeConfirmRequest(BaseModel):
    weight_kg: Decimal | None = Field(default=None, gt=0, decimal_places=3)


class IntakeRejectRequest(BaseModel):
    reason: str = Field(..., min_length=3)


class QRVerifyRequest(BaseModel):
    token: str = Field(..., min_length=16)


class QRVerifyOut(BaseModel):
    valid: bool
    payload: dict


class HarvestIntakeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    koperasi_id: int
    farmer_id: int
    commodity_id: int
    weight_kg: Decimal
    qr_token: str
    status: IntakeStatus
    estimated_value: Decimal | None
    exceeds_pool_flag: bool
    reject_reason: str | None
    price_per_kg: Decimal | None
    total_paid: Decimal | None
    confirmed_by: int | None
    confirmed_at: datetime | None
    created_at: datetime
