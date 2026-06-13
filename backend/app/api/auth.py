"""Authentication router."""
from __future__ import annotations

import logging
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import CurrentUser, get_current_user
from app.core.security import create_access_token, hash_password, verify_password
from app.db.engine import get_session
from app.models.enums import FarmerStatus, UserRole
from app.models.users import Distributor, Farmer, User
from app.schemas.auth import (
    ActivateAccountRequest,
    DistributorSignupRequest,
    LoginRequest,
    SignupRequest,
    TokenResponse,
    UserOut,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


async def _assert_unique_identity(
    session: AsyncSession,
    *,
    email: str | None = None,
    phone: str | None = None,
    nik: str | None = None,
) -> None:
    if email is not None:
        existing_email = await session.execute(select(User).where(User.email == email))
        if existing_email.scalar_one_or_none() is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email is already registered.",
            )

    if phone is not None:
        existing_phone = await session.execute(select(User).where(User.phone == phone))
        if existing_phone.scalar_one_or_none() is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Phone number is already registered.",
            )

    if nik is not None:
        existing_nik = await session.execute(select(Farmer).where(Farmer.nik == nik))
        if existing_nik.scalar_one_or_none() is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="NIK is already registered.",
            )


@router.post(
    "/signup",
    response_model=UserOut,
    status_code=status.HTTP_201_CREATED,
    summary="Register a public user (restricted compatibility endpoint)",
)
async def signup(
    body: SignupRequest,
    session: AsyncSession = Depends(get_session),
) -> UserOut:
    """Compatibility endpoint. Privileged roles are never created publicly."""
    if body.role not in (UserRole.farmer, UserRole.distributor):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Privileged roles cannot be created through public signup.",
        )
    if body.role == UserRole.farmer:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Farmer accounts are created by admin. Use the admin endpoint.",
        )

    await _assert_unique_identity(session, email=str(body.email))
    user = User(
        name=body.name,
        email=str(body.email),
        phone=body.phone,
        role=UserRole.distributor,
        koperasi_id=None,
        password_hash=hash_password(body.password),
        status="active",
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return UserOut.model_validate(user)


@router.post(
    "/signup/distributor",
    response_model=UserOut,
    status_code=status.HTTP_201_CREATED,
    summary="Register a distributor buyer account",
)
async def signup_distributor(
    body: DistributorSignupRequest,
    session: AsyncSession = Depends(get_session),
) -> UserOut:
    await _assert_unique_identity(
        session,
        email=str(body.email) if body.email else None,
        phone=body.phone,
    )

    user = User(
        name=body.name,
        email=str(body.email) if body.email else None,
        phone=body.phone,
        role=UserRole.distributor,
        koperasi_id=None,
        password_hash=hash_password(body.password),
        status="active",
    )
    session.add(user)
    await session.flush()
    session.add(
        Distributor(
            user_id=user.id,
            company_name=body.company_name,
            address=body.address,
        )
    )
    await session.commit()
    await session.refresh(user)
    return UserOut.model_validate(user)


@router.post("/login", response_model=TokenResponse, summary="Login with email or phone + password")
async def login(
    body: LoginRequest,
    session: AsyncSession = Depends(get_session),
) -> TokenResponse:
    return await _authenticate(body.identifier, body.password, session)


@router.post(
    "/login/form",
    response_model=TokenResponse,
    include_in_schema=True,
    summary="Login with OAuth2 form",
)
async def login_form(
    form: OAuth2PasswordRequestForm = Depends(),
    session: AsyncSession = Depends(get_session),
) -> TokenResponse:
    return await _authenticate(form.username, form.password, session)


@router.post(
    "/activate",
    summary="Activate account with token and set password",
)
async def activate_account(
    body: ActivateAccountRequest,
    session: AsyncSession = Depends(get_session),
) -> dict:
    result = await session.execute(
        select(User).where(User.activation_token == body.token)
    )
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid activation token.",
        )

    if user.activation_token_expires_at is not None:
        if user.activation_token_expires_at < datetime.now(UTC):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Activation token has expired.",
            )

    if user.status != "pending_activation":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Account is already activated.",
        )

    user.password_hash = hash_password(body.password)
    user.status = "active"
    user.activation_token = None
    user.activation_token_expires_at = None

    session.add(user)
    await session.commit()

    return {"ok": True, "message": "Akun berhasil diaktifkan."}


@router.get("/me", response_model=UserOut, summary="Get the current user")
async def me(
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> UserOut:
    result = await session.execute(select(User).where(User.id == current_user.user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
    return UserOut.model_validate(user)


async def _authenticate(identifier: str, password: str, session: AsyncSession) -> TokenResponse:
    _401 = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Incorrect credentials.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    result = await session.execute(
        select(User).where(or_(User.email == identifier, User.phone == identifier)).limit(1)
    )
    user = result.scalars().first()
    if user is None or not verify_password(password, user.password_hash):
        raise _401
    if user.status != "active":
        raise _401

    token = create_access_token(
        user_id=user.id,
        role=user.role.value,
        koperasi_id=user.koperasi_id,
    )
    return TokenResponse(access_token=token, token_type="bearer")
