"""
Pydantic v2 schemas for farmer-related endpoints.

FarmerOut — full farmer profile with user fields joined in (name, email, phone).
RejectRequest — body for the admin reject endpoint.
AdminCreateFarmerRequest — body for admin in-person farmer creation.
"""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.enums import FarmerStatus


class FarmerOut(BaseModel):
    """
    Farmer profile returned by admin listing and detail endpoints.

    The name / email / phone fields come from the joined users row.
    They are populated by the service layer which passes a (Farmer, User) tuple
    and constructs this model explicitly — from_attributes=True lets it also
    accept a namedtuple or simple object with the right attribute names.
    """

    model_config = ConfigDict(from_attributes=True)

    # --- Farmer row fields ---
    user_id: int
    koperasi_id: int
    nik: str
    address: str | None
    ktp_photo_url: str | None
    credit_tier: str | None
    status: FarmerStatus
    verified_by: int | None
    verified_at: datetime | None
    created_at: datetime

    # --- Joined from users row ---
    name: str
    email: str | None
    phone: str | None


class RejectRequest(BaseModel):
    """Body for POST /admin/farmers/{user_id}/reject."""

    reason: str = Field(..., min_length=3, description="Rejection reason (min 3 chars)")


class AdminCreateFarmerRequest(BaseModel):
    """Body for POST /admin/farmers — admin creates farmer account in person."""

    name: str = Field(..., min_length=1, max_length=255)
    nik: str = Field(..., pattern=r"^[0-9]{16}$")
    phone: str = Field(..., max_length=20)
    address: str | None = None
    email: EmailStr | None = None
    ktp_photo_url: str | None = None
