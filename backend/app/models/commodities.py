import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Commodity(Base):
    __tablename__ = "commodities"

    id: Mapped[int] = mapped_column(sa.BigInteger, primary_key=True, autoincrement=True)
    koperasi_id: Mapped[int] = mapped_column(
        sa.BigInteger, sa.ForeignKey("koperasi.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    unit: Mapped[str] = mapped_column(sa.String(10), nullable=False, default="kg", server_default="kg")
    pihps_price: Mapped[sa.Numeric] = mapped_column(
        sa.Numeric(18, 2, asdecimal=True), nullable=False
    )
    # cached from stock_movements; updated in the same txn as any stock movement
    current_stock_kg: Mapped[sa.Numeric] = mapped_column(
        sa.Numeric(10, 3, asdecimal=True), nullable=False, default=0, server_default=sa.text("0")
    )
    cold_storage_location: Mapped[str | None] = mapped_column(sa.String(255), nullable=True)
    created_at: Mapped[sa.DateTime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )
