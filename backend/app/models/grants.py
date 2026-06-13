import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.enums import GrantStatus


class DataShareGrant(Base):
    __tablename__ = "data_share_grants"

    id: Mapped[int] = mapped_column(sa.BigInteger, primary_key=True, autoincrement=True)
    koperasi_id: Mapped[int] = mapped_column(
        sa.BigInteger, sa.ForeignKey("koperasi.id"), nullable=False, index=True
    )
    financing_partner_id: Mapped[int] = mapped_column(
        sa.BigInteger, sa.ForeignKey("financing_partners.id"), nullable=False, index=True
    )
    # validated against a Pydantic allow-list in the service layer — never trusted raw
    scope_json: Mapped[dict] = mapped_column(sa.JSON, nullable=False)
    date_range_start: Mapped[sa.Date] = mapped_column(sa.Date, nullable=False)
    date_range_end: Mapped[sa.Date] = mapped_column(sa.Date, nullable=False)
    status: Mapped[GrantStatus] = mapped_column(
        sa.Enum(GrantStatus, name="grant_status", create_type=True, values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
        default=GrantStatus.active,
        server_default="active",
    )
    granted_by: Mapped[int | None] = mapped_column(
        sa.BigInteger, sa.ForeignKey("users.id"), nullable=True
    )
    created_at: Mapped[sa.DateTime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )
