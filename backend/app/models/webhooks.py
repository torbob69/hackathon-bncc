import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.enums import WebhookStatus


class XenditWebhookEvent(Base):
    __tablename__ = "xendit_webhook_events"

    id: Mapped[int] = mapped_column(sa.BigInteger, primary_key=True, autoincrement=True)
    # unique — idempotency inbox key; INSERT … ON CONFLICT (event_id) DO NOTHING
    event_id: Mapped[str] = mapped_column(sa.String(128), nullable=False, unique=True)
    event_type: Mapped[str] = mapped_column(sa.String(100), nullable=False)
    reference_type: Mapped[str | None] = mapped_column(sa.String(50), nullable=True)
    reference_id: Mapped[int | None] = mapped_column(sa.BigInteger, nullable=True)
    payload: Mapped[dict] = mapped_column(sa.JSON, nullable=False)
    status: Mapped[WebhookStatus] = mapped_column(
        sa.Enum(WebhookStatus, name="webhook_status", create_type=True, values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
        default=WebhookStatus.received,
        server_default="received",
    )
    received_at: Mapped[sa.DateTime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )
    processed_at: Mapped[sa.DateTime | None] = mapped_column(
        sa.DateTime(timezone=True), nullable=True
    )
