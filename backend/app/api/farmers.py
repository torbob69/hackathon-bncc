from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.db.engine import get_session
from app.models.enums import FarmerStatus, UserRole
from app.models.users import Farmer, User
from app.schemas.farmers import FarmerOut
from app.services.audit import write_audit
from app.services.storage import get_storage_provider

router = APIRouter(prefix="/farmers", tags=["farmers"])


@router.post("/signup", response_model=FarmerOut, status_code=status.HTTP_201_CREATED)
async def farmer_signup(
    name: str = Form(..., min_length=1, max_length=255),
    email: str = Form(...),
    password: str = Form(..., min_length=8),
    koperasi_id: int = Form(...),
    nik: str = Form(..., pattern=r"^[0-9]{16}$"),
    address: str | None = Form(default=None),
    phone: str | None = Form(default=None, max_length=20),
    ktp_photo: UploadFile | None = File(default=None),
    session: AsyncSession = Depends(get_session),
) -> FarmerOut:
    existing_email = await session.execute(select(User).where(User.email == email))
    if existing_email.scalar_one_or_none() is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email is already registered.")

    existing_nik = await session.execute(select(Farmer).where(Farmer.nik == nik))
    if existing_nik.scalar_one_or_none() is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="NIK is already registered.")

    ktp_photo_url: str | None = None
    if ktp_photo is not None:
        storage = get_storage_provider()
        ktp_photo_url = await storage.upload_file(
            bucket="farmer-documents",
            prefix=f"kop-{koperasi_id}/ktp",
            file=ktp_photo,
        )

    async with session.begin():
        user = User(
            name=name,
            email=email,
            phone=phone,
            role=UserRole.farmer,
            koperasi_id=None,
            password_hash=hash_password(password),
            status="pending",
        )
        session.add(user)
        await session.flush()
        farmer = Farmer(
            user_id=user.id,
            koperasi_id=koperasi_id,
            nik=nik,
            address=address,
            ktp_photo_url=ktp_photo_url,
            status=FarmerStatus.pending,
        )
        session.add(farmer)
        await write_audit(
            session,
            actor_user_id=user.id,
            koperasi_id=koperasi_id,
            action="farmer_signup_submitted",
            entity_type="farmer",
            entity_id=user.id,
            after={"nik": nik, "ktp_photo_url": ktp_photo_url, "status": "pending"},
        )

    return FarmerOut.model_validate(
        {
            "user_id": farmer.user_id,
            "koperasi_id": farmer.koperasi_id,
            "nik": farmer.nik,
            "address": farmer.address,
            "ktp_photo_url": farmer.ktp_photo_url,
            "credit_tier": farmer.credit_tier,
            "status": farmer.status,
            "verified_by": farmer.verified_by,
            "verified_at": farmer.verified_at,
            "created_at": farmer.created_at,
            "name": user.name,
            "email": user.email,
            "phone": user.phone,
        }
    )
