import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Koperasi(Base):
    __tablename__ = "koperasi"

    id: Mapped[int] = mapped_column(sa.BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    type: Mapped[str] = mapped_column(sa.String(100), nullable=False)
    address: Mapped[str] = mapped_column(sa.Text, nullable=False)
    region: Mapped[str] = mapped_column(sa.String(100), nullable=False)
    xendit_account_id: Mapped[str | None] = mapped_column(sa.String(255), nullable=True)
    created_at: Mapped[sa.DateTime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )


class KoperasiFunds(Base):
    __tablename__ = "koperasi_funds"

    koperasi_id: Mapped[int] = mapped_column(
        sa.BigInteger, sa.ForeignKey("koperasi.id"), primary_key=True
    )
    marginal_profit_pool_balance: Mapped[sa.Numeric] = mapped_column(
        sa.Numeric(18, 2, asdecimal=True), nullable=False, default=0, server_default=sa.text("0")
    )
    loan_pool_balance: Mapped[sa.Numeric] = mapped_column(
        sa.Numeric(18, 2, asdecimal=True), nullable=False, default=0, server_default=sa.text("0")
    )
    updated_at: Mapped[sa.DateTime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )
