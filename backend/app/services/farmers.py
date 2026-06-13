"""
Business logic for farmer signup validation (admin workflow).

Design rules (CLAUDE.md §8):
  - Every query is scoped by koperasi_id — a farmer's canonical tenant is
    farmers.koperasi_id, so we filter on that column, not users.koperasi_id.
  - approve_farmer and reject_farmer each write an audit entry via write_audit
    (INSERT-only, does not commit) then commit at the end of the function.
  - All DB access uses SQLAlchemy 2.0 async select().

Enum-limitation note:
  FarmerStatus has only {pending, active} — there is no 'rejected' value.
  For rejection we therefore set users.status = 'rejected' (users.status is a
  free String column) and leave farmers.status = 'pending' so the farmer
  cannot log in with an active session but the farmers row is not silently
  dropped.  This choice is documented here and recorded in the audit log.
  If FarmerStatus gains a 'rejected' value in a future migration, update this
  function accordingly.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import FarmerStatus
from app.models.users import Farmer, User
from app.services.audit import write_audit

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Read helpers
# ---------------------------------------------------------------------------


async def list_farmers(
    session: AsyncSession,
    koperasi_id: int,
    status_filter: FarmerStatus | None = None,
) -> list[tuple[Farmer, User]]:
    """
    Return all farmers belonging to *koperasi_id*, optionally filtered by
    farmer status.

    Returns a list of (Farmer, User) tuples — callers build FarmerOut from
    both objects.
    """
    stmt = (
        select(Farmer, User)
        .join(User, User.id == Farmer.user_id)
        .where(Farmer.koperasi_id == koperasi_id)
    )
    if status_filter is not None:
        stmt = stmt.where(Farmer.status == status_filter)

    result = await session.execute(stmt)
    return list(result.tuples().all())


async def get_farmer(
    session: AsyncSession,
    koperasi_id: int,
    user_id: int,
) -> tuple[Farmer, User] | None:
    """
    Fetch a single farmer (tenant-scoped by koperasi_id).

    Returns (Farmer, User) tuple or None if not found / belongs to a different
    koperasi.  The router converts None → HTTP 404.
    """
    stmt = (
        select(Farmer, User)
        .join(User, User.id == Farmer.user_id)
        .where(Farmer.koperasi_id == koperasi_id, Farmer.user_id == user_id)
    )
    result = await session.execute(stmt)
    row = result.tuples().first()
    return row if row is not None else None


# ---------------------------------------------------------------------------
# Write helpers
# ---------------------------------------------------------------------------


async def approve_farmer(
    session: AsyncSession,
    koperasi_id: int,
    user_id: int,
    admin_user_id: int,
) -> tuple[Farmer, User]:
    """
    Approve a pending farmer signup.

    Steps (all within one transaction):
      1. Load and tenant-scope-check the farmer row.
      2. Reject (raise 409) if farmer is not pending.
      3. Set Farmer.status = active, Farmer.verified_by, Farmer.verified_at.
      4. Set the linked User.status = 'active'.
      5. Write audit entry (action='farmer_approved').
      6. Commit.

    Returns the updated (Farmer, User) tuple.

    Raises:
        HTTP 404 — farmer not found or belongs to a different koperasi.
        HTTP 409 — farmer is not in pending state.
    """
    row = await get_farmer(session, koperasi_id, user_id)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Farmer {user_id} not found in this koperasi.",
        )

    farmer, user = row

    if farmer.status != FarmerStatus.pending:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Farmer is not pending (current status: {farmer.status.value}).",
        )

    # Snapshot before state for the audit trail
    before = {
        "farmer_status": farmer.status.value,
        "user_status": user.status,
        "verified_by": farmer.verified_by,
        "verified_at": farmer.verified_at,
    }

    now_utc = datetime.now(timezone.utc)
    farmer.status = FarmerStatus.active
    farmer.verified_by = admin_user_id
    farmer.verified_at = now_utc
    user.status = "active"

    after = {
        "farmer_status": farmer.status.value,
        "user_status": user.status,
        "verified_by": farmer.verified_by,
        "verified_at": farmer.verified_at,
    }

    session.add(farmer)
    session.add(user)

    await write_audit(
        session,
        actor_user_id=admin_user_id,
        koperasi_id=koperasi_id,
        action="farmer_approved",
        entity_type="farmer",
        entity_id=user_id,
        before=before,
        after=after,
    )

    await session.commit()
    # Refresh to get server-side defaults reflected on the ORM objects
    await session.refresh(farmer)
    await session.refresh(user)

    logger.info(
        "farmer approved: user_id=%s koperasi_id=%s by admin=%s",
        user_id,
        koperasi_id,
        admin_user_id,
    )
    return farmer, user


async def reject_farmer(
    session: AsyncSession,
    koperasi_id: int,
    user_id: int,
    admin_user_id: int,
    reason: str,
) -> tuple[Farmer, User]:
    """
    Reject a farmer signup application.

    Enum-limitation: FarmerStatus has no 'rejected' value (only pending/active).
    We therefore set users.status = 'rejected' (a free String column) so the
    account cannot be used, while leaving farmers.status = 'pending' to
    preserve the application record.  The rejection reason is recorded in the
    audit log's after_json.  See module docstring for rationale.

    Steps (all within one transaction):
      1. Load and tenant-scope-check the farmer row.
      2. Raise 404 if not found.  Allow rejecting an already-pending farmer only
         (idempotent-friendly: raise 409 if already active).
      3. Set User.status = 'rejected'.
      4. Write audit entry (action='farmer_rejected', after includes reason).
      5. Commit.

    Returns the (Farmer, User) tuple after the update.

    Raises:
        HTTP 404 — farmer not found or belongs to a different koperasi.
        HTTP 409 — farmer is already active (cannot reject an active member).
    """
    row = await get_farmer(session, koperasi_id, user_id)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Farmer {user_id} not found in this koperasi.",
        )

    farmer, user = row

    if farmer.status == FarmerStatus.active:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot reject a farmer who is already active.",
        )

    before = {
        "farmer_status": farmer.status.value,
        "user_status": user.status,
    }

    # FarmerStatus has no 'rejected' — record rejection on the User row only
    user.status = "rejected"
    # farmers.status remains 'pending' intentionally (enum limitation)

    after = {
        "farmer_status": farmer.status.value,  # still 'pending'
        "user_status": user.status,            # now 'rejected'
        "reason": reason,
    }

    session.add(user)

    await write_audit(
        session,
        actor_user_id=admin_user_id,
        koperasi_id=koperasi_id,
        action="farmer_rejected",
        entity_type="farmer",
        entity_id=user_id,
        before=before,
        after=after,
    )

    await session.commit()
    await session.refresh(farmer)
    await session.refresh(user)

    logger.info(
        "farmer rejected: user_id=%s koperasi_id=%s by admin=%s reason=%r",
        user_id,
        koperasi_id,
        admin_user_id,
        reason,
    )
    return farmer, user
