import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.enums import FulfillmentType, OrderStatus, PaymentChannel, PaymentStatus


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(sa.BigInteger, primary_key=True, autoincrement=True)
    koperasi_id: Mapped[int] = mapped_column(
        sa.BigInteger, sa.ForeignKey("koperasi.id"), nullable=False, index=True
    )
    distributor_id: Mapped[int] = mapped_column(
        sa.BigInteger, sa.ForeignKey("distributors.user_id"), nullable=False, index=True
    )
    status: Mapped[OrderStatus] = mapped_column(
        sa.Enum(OrderStatus, name="order_status", create_type=True, values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
        default=OrderStatus.pending,
        server_default="pending",
    )
    fulfillment_type: Mapped[FulfillmentType] = mapped_column(
        sa.Enum(FulfillmentType, name="fulfillment_type", create_type=True, values_callable=lambda obj: [e.value for e in obj]), nullable=False
    )
    delivery_address: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    subtotal: Mapped[sa.Numeric] = mapped_column(
        sa.Numeric(18, 2, asdecimal=True), nullable=False
    )
    platform_fee: Mapped[sa.Numeric] = mapped_column(
        sa.Numeric(18, 2, asdecimal=True), nullable=False
    )
    total: Mapped[sa.Numeric] = mapped_column(
        sa.Numeric(18, 2, asdecimal=True), nullable=False
    )
    xendit_invoice_id: Mapped[str | None] = mapped_column(
        sa.String(255), nullable=True, unique=True
    )
    payment_channel: Mapped[PaymentChannel | None] = mapped_column(
        sa.Enum(PaymentChannel, name="payment_channel", create_type=True, values_callable=lambda obj: [e.value for e in obj]), nullable=True
    )
    payment_status: Mapped[PaymentStatus | None] = mapped_column(
        sa.Enum(PaymentStatus, name="payment_status", create_type=True, values_callable=lambda obj: [e.value for e in obj]), nullable=True
    )
    # VARCHAR(512) per spec — signed pickup QR token
    pickup_qr_token: Mapped[str | None] = mapped_column(
        sa.String(512), nullable=True, unique=True
    )
    created_at: Mapped[sa.DateTime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )


class OrderItem(Base):
    __tablename__ = "order_items"

    id: Mapped[int] = mapped_column(sa.BigInteger, primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column(
        sa.BigInteger, sa.ForeignKey("orders.id"), nullable=False, index=True
    )
    # tenant-safe direct queries — service asserts commodity.koperasi_id == orders.koperasi_id
    koperasi_id: Mapped[int] = mapped_column(
        sa.BigInteger, sa.ForeignKey("koperasi.id"), nullable=False, index=True
    )
    commodity_id: Mapped[int] = mapped_column(
        sa.BigInteger, sa.ForeignKey("commodities.id"), nullable=False
    )
    weight_kg: Mapped[sa.Numeric] = mapped_column(
        sa.Numeric(10, 3, asdecimal=True), nullable=False
    )
    price_per_kg: Mapped[sa.Numeric] = mapped_column(
        sa.Numeric(18, 2, asdecimal=True), nullable=False
    )
    line_total: Mapped[sa.Numeric] = mapped_column(
        sa.Numeric(18, 2, asdecimal=True), nullable=False
    )
