"""
Admin — Farmer Signup Validation endpoints.

Router prefix : /admin/farmers
Tags          : ["admin:farmers"]
Auth          : every endpoint requires UserRole.admin (via Depends(require_role))
Tenant        : resolved from the admin's JWT via get_tenant_id(current_user)

Endpoints:
  POST   /admin/farmers              — admin creates farmer account in-person
  GET    /admin/farmers              — list farmers (optional ?status= filter)
  GET    /admin/farmers/{user_id}    — get single farmer profile
  POST   /admin/farmers/{user_id}/approve — approve a pending farmer
  POST   /admin/farmers/{user_id}/reject  — reject a pending farmer

Business logic lives in app.services.farmers; this module is a thin HTTP layer.
"""
from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.deps import CurrentUser, get_tenant_id, require_role
from app.db.engine import get_session
from app.models.enums import FarmerStatus, UserRole
from app.schemas.farmers import AdminCreateFarmerRequest, FarmerOut, RejectRequest
from app.services import farmers as farmer_service
from app.services import notifier

router = APIRouter(prefix="/admin/farmers", tags=["admin:farmers"])

# ---------------------------------------------------------------------------
# Utility: build FarmerOut from a (Farmer, User) tuple
# ---------------------------------------------------------------------------


def _to_farmer_out(farmer_row, user_row) -> FarmerOut:
    """
    Construct FarmerOut from the two ORM objects returned by the service layer.
    Using model_validate with a plain dict is the most explicit approach and
    avoids any attribute-name ambiguity between the two objects.
    """
    return FarmerOut.model_validate(
        {
            "user_id": farmer_row.user_id,
            "koperasi_id": farmer_row.koperasi_id,
            "nik": farmer_row.nik,
            "address": farmer_row.address,
            "ktp_photo_url": farmer_row.ktp_photo_url,
            "credit_tier": farmer_row.credit_tier,
            "status": farmer_row.status,
            "verified_by": farmer_row.verified_by,
            "verified_at": farmer_row.verified_at,
            "created_at": farmer_row.created_at,
            # From joined User row
            "name": user_row.name,
            "email": user_row.email,
            "phone": user_row.phone,
        }
    )


# ---------------------------------------------------------------------------
# POST /admin/farmers  (create farmer in-person)
# ---------------------------------------------------------------------------


@router.post(
    "",
    response_model=FarmerOut,
    status_code=status.HTTP_201_CREATED,
    summary="Admin creates a farmer account (sends activation link)",
)
async def create_farmer(
    body: AdminCreateFarmerRequest,
    background_tasks: BackgroundTasks,
    current_user: CurrentUser = Depends(require_role(UserRole.admin)),
    session: AsyncSession = Depends(get_session),
) -> FarmerOut:
    """
    Create a farmer account in-person.

    - Admin verifies identity on the spot; farmer status is set to active
      immediately (no further approval step needed).
    - A time-limited activation token is generated and sent to the farmer
      via email and/or WhatsApp so they can set their password.
    - Returns the new farmer profile.
    """
    koperasi_id = get_tenant_id(current_user)

    # Generate activation token
    token = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(hours=settings.ACTIVATION_TOKEN_EXPIRE_HOURS)

    farmer, user = await farmer_service.create_farmer(
        session,
        koperasi_id,
        current_user.user_id,
        name=body.name,
        nik=body.nik,
        address=body.address,
        phone=body.phone,
        email=str(body.email) if body.email else None,
        ktp_photo_url=body.ktp_photo_url,
        activation_token=token,
        activation_token_expires_at=expires_at,
    )

    activation_url = f"{settings.FRONTEND_URL}/activate?token={token}"

    background_tasks.add_task(notifier.send_activation_whatsapp, body.phone, activation_url, body.name)

    return _to_farmer_out(farmer, user)


# ---------------------------------------------------------------------------
# GET /admin/farmers
# ---------------------------------------------------------------------------


@router.get("", response_model=list[FarmerOut], summary="List farmers (admin)")
async def list_farmers(
    status: Optional[FarmerStatus] = Query(
        default=None,
        description="Filter by farmer status: pending | active",
    ),
    current_user: CurrentUser = Depends(require_role(UserRole.admin)),
    session: AsyncSession = Depends(get_session),
) -> list[FarmerOut]:
    """
    Return all farmers in the admin's koperasi, optionally filtered by status.

    - Pass `?status=pending` to see all applications awaiting validation.
    - Pass `?status=active` to see approved members.
    - Omit the parameter to return all farmers.
    """
    koperasi_id = get_tenant_id(current_user)
    rows = await farmer_service.list_farmers(session, koperasi_id, status)
    return [_to_farmer_out(f, u) for f, u in rows]


# ---------------------------------------------------------------------------
# GET /admin/farmers/{user_id}
# ---------------------------------------------------------------------------


@router.get(
    "/{user_id}",
    response_model=FarmerOut,
    summary="Get farmer detail (admin)",
)
async def get_farmer(
    user_id: int,
    current_user: CurrentUser = Depends(require_role(UserRole.admin)),
    session: AsyncSession = Depends(get_session),
) -> FarmerOut:
    """Return the profile for a single farmer in the admin's koperasi."""
    koperasi_id = get_tenant_id(current_user)
    row = await farmer_service.get_farmer(session, koperasi_id, user_id)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Farmer {user_id} not found in this koperasi.",
        )
    farmer, user = row
    return _to_farmer_out(farmer, user)


# ---------------------------------------------------------------------------
# POST /admin/farmers/{user_id}/approve
# ---------------------------------------------------------------------------


@router.post(
    "/{user_id}/approve",
    response_model=FarmerOut,
    summary="Approve a pending farmer signup",
)
async def approve_farmer(
    user_id: int,
    request: Request,
    current_user: CurrentUser = Depends(require_role(UserRole.admin)),
    session: AsyncSession = Depends(get_session),
) -> FarmerOut:
    """
    Approve a farmer's signup application.

    - Farmer must be in `pending` status (409 if already active).
    - Sets `farmers.status = active`, records `verified_by` / `verified_at`,
      activates the linked `users` row, and writes an audit log entry.
    - Returns the updated farmer profile.
    """
    koperasi_id = get_tenant_id(current_user)
    farmer, user = await farmer_service.approve_farmer(
        session,
        koperasi_id=koperasi_id,
        user_id=user_id,
        admin_user_id=current_user.user_id,
    )
    return _to_farmer_out(farmer, user)


# ---------------------------------------------------------------------------
# POST /admin/farmers/{user_id}/reject
# ---------------------------------------------------------------------------


@router.post(
    "/{user_id}/reject",
    summary="Reject a pending farmer signup",
)
async def reject_farmer(
    user_id: int,
    body: RejectRequest,
    request: Request,
    current_user: CurrentUser = Depends(require_role(UserRole.admin)),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """
    Reject a farmer's signup application.

    - The reason must be at least 3 characters.
    - Sets `users.status = 'rejected'` (farmers.status stays 'pending' because
      FarmerStatus enum has no 'rejected' value — see services/farmers.py).
    - Writes an audit log entry with the rejection reason.
    - Returns `{ok: true, message: ...}`.
    """
    koperasi_id = get_tenant_id(current_user)
    await farmer_service.reject_farmer(
        session,
        koperasi_id=koperasi_id,
        user_id=user_id,
        admin_user_id=current_user.user_id,
        reason=body.reason,
    )
    return {"ok": True, "message": f"Farmer {user_id} has been rejected."}
