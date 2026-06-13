import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.enums import FarmerStatus, UserRole


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(sa.BigInteger, primary_key=True, autoincrement=True)
    # koperasi_id is set for manager/admin only; null for farmer, distributor, financing_partner, platform_admin
    koperasi_id: Mapped[int | None] = mapped_column(
        sa.BigInteger, sa.ForeignKey("koperasi.id"), nullable=True, index=True
    )
    role: Mapped[UserRole] = mapped_column(
        sa.Enum(UserRole, name="user_role", create_type=True, values_callable=lambda obj: [e.value for e in obj]), nullable=False
    )
    name: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    email: Mapped[str] = mapped_column(sa.String(255), nullable=False, unique=True)
    phone: Mapped[str | None] = mapped_column(sa.String(20), nullable=True)
    password_hash: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    status: Mapped[str] = mapped_column(sa.String(50), nullable=False, default="active", server_default="active")
    created_at: Mapped[sa.DateTime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )


class Farmer(Base):
    __tablename__ = "farmers"

    # user_id is both PK and FK — one-to-one with users
    user_id: Mapped[int] = mapped_column(
        sa.BigInteger, sa.ForeignKey("users.id"), primary_key=True, unique=True
    )
    # canonical tenant for a farmer — single source of truth
    koperasi_id: Mapped[int] = mapped_column(
        sa.BigInteger, sa.ForeignKey("koperasi.id"), nullable=False, index=True
    )
    nik: Mapped[str] = mapped_column(sa.String(16), nullable=False, unique=True)
    address: Mapped[str] = mapped_column(sa.Text, nullable=True)
    ktp_photo_url: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    credit_tier: Mapped[str | None] = mapped_column(sa.String(10), nullable=True)
    status: Mapped[FarmerStatus] = mapped_column(
        sa.Enum(FarmerStatus, name="farmer_status", create_type=True, values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
        default=FarmerStatus.pending,
        server_default="pending",
    )
    verified_by: Mapped[int | None] = mapped_column(
        sa.BigInteger, sa.ForeignKey("users.id"), nullable=True
    )
    verified_at: Mapped[sa.DateTime | None] = mapped_column(
        sa.DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[sa.DateTime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )

    __table_args__ = (
        sa.CheckConstraint("nik ~ '^[0-9]{16}$'", name="chk_nik_format"),
    )


class Distributor(Base):
    __tablename__ = "distributors"

    user_id: Mapped[int] = mapped_column(
        sa.BigInteger, sa.ForeignKey("users.id"), primary_key=True, unique=True
    )
    company_name: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    address: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    created_at: Mapped[sa.DateTime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )


class FinancingPartner(Base):
    __tablename__ = "financing_partners"

    id: Mapped[int] = mapped_column(sa.BigInteger, primary_key=True, autoincrement=True)
    # login bridge — each financing partner maps to a users row
    user_id: Mapped[int] = mapped_column(
        sa.BigInteger, sa.ForeignKey("users.id"), nullable=False, unique=True
    )
    name: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    contact_email: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    created_at: Mapped[sa.DateTime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )
