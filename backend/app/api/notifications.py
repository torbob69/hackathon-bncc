"""
Notifications API router.

Prefix  : /notifications
Tags    : notifications

Endpoints
---------
GET  /notifications                        — List own notifications; optional ?unread_only=bool.
GET  /notifications/unread-count           — Return {"unread": int} for the caller.
POST /notifications/{notification_id}/read — Mark a single own notification as read.
POST /notifications/read-all               — Mark all own unread notifications as read.

Scoping rules (CLAUDE.md §3.2 / §8):
  - Every query is filtered by user_id == current_user.user_id.
  - Any authenticated role may use these endpoints (farmer, manager, admin,
    distributor, financing_partner, platform_admin all receive notifications).
  - A user can NEVER read or modify another user's notifications — ownership is
    checked before every write; 404 is returned (not 403) to avoid leaking
    existence of foreign notifications.

Transaction discipline:
  - Read endpoints are plain SELECTs — no begin() needed.
  - Write endpoints (mark-read / read-all) use `async with session.begin()`.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import CurrentUser, get_current_user
from app.db.engine import get_session
from app.models.notifications import Notification
from app.schemas.notifications import NotificationOut

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/notifications", tags=["notifications"])


# ---------------------------------------------------------------------------
# GET /notifications  — list own notifications
# ---------------------------------------------------------------------------


@router.get(
    "",
    response_model=list[NotificationOut],
    summary="List own notifications, ordered newest first",
)
async def list_notifications(
    unread_only: bool = False,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[NotificationOut]:
    """
    Return notifications for the authenticated user, newest first.

    Query parameters:
      - unread_only — if true, only return notifications where is_read=False.

    Always scoped to the caller's user_id — never returns another user's
    notifications.
    """
    query = (
        select(Notification)
        .where(Notification.user_id == current_user.user_id)
        .order_by(Notification.created_at.desc())
    )

    if unread_only:
        query = query.where(Notification.is_read.is_(False))

    result = await session.execute(query)
    rows = result.scalars().all()
    return [NotificationOut.model_validate(row) for row in rows]


# ---------------------------------------------------------------------------
# GET /notifications/unread-count  — unread count for the caller
#
# IMPORTANT: declared BEFORE /{notification_id} so FastAPI matches the
# literal path segment "unread-count" rather than treating it as an int.
# ---------------------------------------------------------------------------


@router.get(
    "/unread-count",
    summary="Return unread notification count for the caller",
)
async def get_unread_count(
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, int]:
    """
    Return a simple count of unread notifications for the authenticated user.

    Response: {"unread": <int>}
    """
    result = await session.execute(
        select(func.count())
        .select_from(Notification)
        .where(
            Notification.user_id == current_user.user_id,
            Notification.is_read.is_(False),
        )
    )
    count = result.scalar_one()
    return {"unread": count}


# ---------------------------------------------------------------------------
# POST /notifications/read-all  — bulk mark-read
#
# IMPORTANT: declared BEFORE /{notification_id}/read so FastAPI matches the
# literal path segment "read-all" rather than treating it as an int.
# ---------------------------------------------------------------------------


@router.post(
    "/read-all",
    summary="Mark all own unread notifications as read",
)
async def mark_all_read(
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, int]:
    """
    Set is_read=True on every unread notification belonging to the caller.

    Response: {"updated": <number of rows changed>}
    """
    async with session.begin():
        result = await session.execute(
            update(Notification)
            .where(
                Notification.user_id == current_user.user_id,
                Notification.is_read.is_(False),
            )
            .values(is_read=True)
            .returning(Notification.id)
        )
        updated_ids = result.fetchall()

    updated_count = len(updated_ids)
    logger.debug(
        "mark_all_read: user=%d updated=%d",
        current_user.user_id,
        updated_count,
    )
    return {"updated": updated_count}


# ---------------------------------------------------------------------------
# POST /notifications/{notification_id}/read  — mark single notification read
# ---------------------------------------------------------------------------


@router.post(
    "/{notification_id}/read",
    response_model=NotificationOut,
    summary="Mark a single own notification as read",
)
async def mark_one_read(
    notification_id: int,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> NotificationOut:
    """
    Mark a specific notification as read.

    Ownership is verified: if the notification does not exist OR belongs to
    a different user, HTTP 404 is returned (avoids leaking existence of
    foreign notifications).

    Returns the updated NotificationOut.
    """
    async with session.begin():
        result = await session.execute(
            select(Notification).where(
                Notification.id == notification_id,
                Notification.user_id == current_user.user_id,
            )
        )
        notification = result.scalar_one_or_none()

        if notification is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Notification {notification_id} not found.",
            )

        notification.is_read = True
        await session.flush()

    logger.debug(
        "mark_one_read: user=%d notification=%d",
        current_user.user_id,
        notification_id,
    )
    return NotificationOut.model_validate(notification)
