import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(sa.BigInteger, primary_key=True, autoincrement=True)
    koperasi_id: Mapped[int | None] = mapped_column(
        sa.BigInteger, sa.ForeignKey("koperasi.id"), nullable=True, index=True
    )
    actor_user_id: Mapped[int | None] = mapped_column(
        sa.BigInteger, sa.ForeignKey("users.id"), nullable=True
    )
    action: Mapped[str] = mapped_column(sa.String(100), nullable=False)
    entity_type: Mapped[str] = mapped_column(sa.String(100), nullable=False)
    entity_id: Mapped[int | None] = mapped_column(sa.BigInteger, nullable=True)
    before_json: Mapped[dict | None] = mapped_column(sa.JSON, nullable=True)
    after_json: Mapped[dict | None] = mapped_column(sa.JSON, nullable=True)
    ip: Mapped[str | None] = mapped_column(sa.String(45), nullable=True)
    created_at: Mapped[sa.DateTime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )
    # Phase 15: app DB role gets INSERT/SELECT only + BEFORE UPDATE/DELETE trigger added via migration
