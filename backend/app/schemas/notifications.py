"""
Pydantic v2 schemas for the notifications API.

NotificationOut is the single response shape used across all notification
endpoints. The type field uses the NotificationType enum from models/enums.py.
"""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.enums import NotificationType


class NotificationOut(BaseModel):
    """
    Single notification row returned by list / read endpoints.

    All fields map 1-to-1 to the notifications table columns.
    reference_type and reference_id are nullable — not every notification
    links to a specific domain entity.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    koperasi_id: int
    user_id: int
    type: NotificationType
    reference_type: str | None
    reference_id: int | None
    message: str
    is_read: bool
    created_at: datetime
