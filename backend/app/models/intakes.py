import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.enums import IntakeStatus, StockDirection


class HarvestIntake(Base):
    __tablename__ = "harvest_intakes"

    id: Mapped[int] = mapped_column(sa.BigInteger, primary_key=True, autoincrement=True)
    koperasi_id: Mapped[int] = mapped_column(
        sa.BigInteger, sa.ForeignKey("koperasi.id"), nullable=False, index=True
    )
    farmer_id: Mapped[int] = mapped_column(
        sa.BigInteger, sa.ForeignKey("farmers.user_id"), nullable=False, index=True
    )
    commodity_id: Mapped[int] = mapped_column(
        sa.BigInteger, sa.ForeignKey("commodities.id"), nullable=False
    )
    weight_kg: Mapped[sa.Numeric] = mapped_column(
        sa.Numeric(10, 3, asdecimal=True), nullable=False
    )
    # JWT-signed payload; Text to avoid VARCHAR(255) limit
    qr_token: Mapped[str] = mapped_column(sa.Text, nullable=False, unique=True)
    status: Mapped[IntakeStatus] = mapped_column(
        sa.Enum(IntakeStatus, name="intake_status", create_type=True, values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
        default=IntakeStatus.pending,
        server_default="pending",
    )
    estimated_value: Mapped[sa.Numeric | None] = mapped_column(
        sa.Numeric(18, 2, asdecimal=True), nullable=True
    )
    exceeds_pool_flag: Mapped[bool] = mapped_column(
        sa.Boolean, nullable=False, default=False, server_default=sa.false()
    )
    reject_reason: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    # system-set from commodities.pihps_price at confirm — never from request
    price_per_kg: Mapped[sa.Numeric | None] = mapped_column(
        sa.Numeric(18, 2, asdecimal=True), nullable=True
    )
    total_paid: Mapped[sa.Numeric | None] = mapped_column(
        sa.Numeric(18, 2, asdecimal=True), nullable=True
    )
    confirmed_by: Mapped[int | None] = mapped_column(
        sa.BigInteger, sa.ForeignKey("users.id"), nullable=True
    )
    confirmed_at: Mapped[sa.DateTime | None] = mapped_column(
        sa.DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[sa.DateTime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )


class StockMovement(Base):
    __tablename__ = "stock_movements"

    id: Mapped[int] = mapped_column(sa.BigInteger, primary_key=True, autoincrement=True)
    koperasi_id: Mapped[int] = mapped_column(
        sa.BigInteger, sa.ForeignKey("koperasi.id"), nullable=False, index=True
    )
    commodity_id: Mapped[int] = mapped_column(
        sa.BigInteger, sa.ForeignKey("commodities.id"), nullable=False
    )
    direction: Mapped[StockDirection] = mapped_column(
        sa.Enum(StockDirection, name="stock_direction", create_type=True, values_callable=lambda obj: [e.value for e in obj]), nullable=False
    )
    weight_kg: Mapped[sa.Numeric] = mapped_column(
        sa.Numeric(10, 3, asdecimal=True), nullable=False
    )
    reference_type: Mapped[str | None] = mapped_column(sa.String(50), nullable=True)
    reference_id: Mapped[int | None] = mapped_column(sa.BigInteger, nullable=True)
    qr_token: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    created_by: Mapped[int | None] = mapped_column(
        sa.BigInteger, sa.ForeignKey("users.id"), nullable=True
    )
    created_at: Mapped[sa.DateTime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )
