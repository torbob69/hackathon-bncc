"""
Authentication router — /auth/signup, /auth/login, /auth/me.

Design notes:
  - POST /auth/signup is a demo/seed endpoint allowing any role to be created
    directly.  In production a more restrictive invite flow would be layered on
    top, but for the hackathon demo this is sufficient.
  - POST /auth/login accepts BOTH:
      * JSON body (LoginRequest) for programmatic clients.
      * OAuth2 form body (application/x-www-form-urlencoded) so that the
        Swagger UI "Authorize" button works out of the box.
  - Farmer profile rows (farmers table) are created in a separate onboarding
    flow (api/farmers.py); the signup here only creates the users row.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import CurrentUser, get_current_user
from app.core.security import create_access_token, hash_password, verify_password
from app.db.engine import get_session
from app.models.enums import UserRole
from app.models.users import User
from app.schemas.auth import LoginRequest, SignupRequest, TokenResponse, UserOut

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


# ---------------------------------------------------------------------------
# POST /auth/signup
# ---------------------------------------------------------------------------


@router.post(
    "/signup",
    response_model=UserOut,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user (demo/seed endpoint)",
)
async def signup(
    body: SignupRequest,
    session: AsyncSession = Depends(get_session),
) -> UserOut:
    """
    Create a new users row.

    - Duplicate email → 409.
    - role manager/admin → koperasi_id required (validated in SignupRequest).
    - role farmer → koperasi_id is ignored here (farmer profile created separately).
    """
    # Check for duplicate email
    existing = await session.execute(select(User).where(User.email == body.email))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Email '{body.email}' is already registered.",
        )

    # For farmer/distributor/financing_partner/platform_admin the koperasi_id
    # stored on users is always null (tenant resolved differently per CLAUDE.md).
    store_koperasi_id: int | None = None
    if body.role in (UserRole.manager, UserRole.admin):
        store_koperasi_id = body.koperasi_id  # validated non-null by SignupRequest

    user = User(
        name=body.name,
        email=body.email,
        phone=body.phone,
        role=body.role,
        koperasi_id=store_koperasi_id,
        password_hash=hash_password(body.password),
        status="active",
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)

    logger.info("New user created: id=%d role=%s", user.id, user.role)
    return UserOut.model_validate(user)


# ---------------------------------------------------------------------------
# POST /auth/login  (JSON body)
# ---------------------------------------------------------------------------


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Login with email + password (JSON)",
)
async def login(
    body: LoginRequest,
    session: AsyncSession = Depends(get_session),
) -> TokenResponse:
    """
    Verify credentials and return a JWT.

    Returns HTTP 401 for wrong email or wrong password (same message to avoid
    user-enumeration).
    """
    return await _authenticate(str(body.email), body.password, session)


# ---------------------------------------------------------------------------
# POST /auth/login  (OAuth2 form — enables Swagger Authorize)
# ---------------------------------------------------------------------------


@router.post(
    "/login/form",
    response_model=TokenResponse,
    include_in_schema=True,
    summary="Login with OAuth2 form (Swagger Authorize)",
)
async def login_form(
    form: OAuth2PasswordRequestForm = Depends(),
    session: AsyncSession = Depends(get_session),
) -> TokenResponse:
    """
    OAuth2 password flow endpoint.  *username* field = email.

    The OAuth2PasswordBearer scheme in deps.py points to /auth/login, so
    Swagger sends the form here.  This makes the Authorize button work.
    """
    return await _authenticate(form.username, form.password, session)


# ---------------------------------------------------------------------------
# GET /auth/me
# ---------------------------------------------------------------------------


@router.get(
    "/me",
    response_model=UserOut,
    summary="Get the currently authenticated user",
)
async def me(
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> UserOut:
    """Return the full UserOut for the authenticated caller."""
    result = await session.execute(select(User).where(User.id == current_user.user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found.",
        )
    return UserOut.model_validate(user)


# ---------------------------------------------------------------------------
# Internal helper
# ---------------------------------------------------------------------------


async def _authenticate(
    email: str, password: str, session: AsyncSession
) -> TokenResponse:
    """
    Shared credential-verification logic for JSON and form-based login.

    Returns a TokenResponse on success; raises HTTP 401 on any failure.
    Same error message regardless of whether email or password was wrong
    (prevents user enumeration).
    """
    _401 = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Incorrect email or password.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    result = await session.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if user is None or not verify_password(password, user.password_hash):
        raise _401

    token = create_access_token(
        user_id=user.id,
        role=user.role.value,
        koperasi_id=user.koperasi_id,
    )
    return TokenResponse(access_token=token, token_type="bearer")
