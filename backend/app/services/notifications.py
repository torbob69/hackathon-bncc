from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import NotificationType, UserRole
from app.models.notifications import Notification
from app.models.users import User


async def create_notification(
    session: AsyncSession,
    *,
    koperasi_id: int,
    user_id: int,
    type: NotificationType,  # noqa: A002
    message: str,
    reference_type: str | None = None,
    reference_id: int | None = None,
) -> Notification:
    notification = Notification(
        koperasi_id=koperasi_id,
        user_id=user_id,
        type=type,
        reference_type=reference_type,
        reference_id=reference_id,
        message=message,
    )
    session.add(notification)
    await session.flush()
    return notification


async def notify_tenant_managers(
    session: AsyncSession,
    *,
    koperasi_id: int,
    type: NotificationType,  # noqa: A002
    message: str,
    reference_type: str | None = None,
    reference_id: int | None = None,
) -> list[Notification]:
    result = await session.execute(
        select(User.id).where(
            User.koperasi_id == koperasi_id,
            User.role.in_([UserRole.manager, UserRole.admin]),
        )
    )
    notifications: list[Notification] = []
    for user_id in result.scalars().all():
        notifications.append(
            await create_notification(
                session,
                koperasi_id=koperasi_id,
                user_id=user_id,
                type=type,
                message=message,
                reference_type=reference_type,
                reference_id=reference_id,
            )
        )
    return notifications
