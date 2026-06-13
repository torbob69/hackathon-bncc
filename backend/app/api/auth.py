"""Authentication router."""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import CurrentUser, get_current_user
from app.core.security import create_access_token, hash_password, verify_password
from app.db.engine import get_session
from app.models.enums import FarmerStatus, UserRole
from app.models.users import Distributor, Farmer, User
from app.schemas.auth import (
    DistributorSignupRequest,
    FarmerSignupRequest,
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
    email: str,
    nik: str | None = None,
) -> None:
    existing_email = await session.execute(select(User).where(User.email == email))
    if existing_email.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email is already registered.",
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
            detail="Use /auth/signup/farmer so the farmer profile is created.",
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
    "/signup/farmer",
    response_model=UserOut,
    status_code=status.HTTP_201_CREATED,
    summary="Submit a farmer membership application",
)
async def signup_farmer(
    body: FarmerSignupRequest,
    session: AsyncSession = Depends(get_session),
) -> UserOut:
    await _assert_unique_identity(session, email=str(body.email), nik=body.nik)

    user = User(
        name=body.name,
        email=str(body.email),
        phone=body.phone,
        role=UserRole.farmer,
        koperasi_id=None,
        password_hash=hash_password(body.password),
        status="pending",
    )
    session.add(user)
    await session.flush()

    session.add(
        Farmer(
            user_id=user.id,
            koperasi_id=body.koperasi_id,
            nik=body.nik,
            address=body.address,
            ktp_photo_url=body.ktp_photo_url,
            status=FarmerStatus.pending,
        )
    )
    await session.commit()
    await session.refresh(user)
    logger.info("Farmer application created: user_id=%d koperasi_id=%d", user.id, body.koperasi_id)
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


@router.post("/login", response_model=TokenResponse, summary="Login with email + password")
async def login(
    body: LoginRequest,
    session: AsyncSession = Depends(get_session),
) -> TokenResponse:
    return await _authenticate(str(body.email), body.password, session)


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


async def _authenticate(email: str, password: str, session: AsyncSession) -> TokenResponse:
    _401 = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Incorrect email or password.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    result = await session.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
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
