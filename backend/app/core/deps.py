"""
FastAPI dependency layer — authentication, tenant scoping, and RBAC.

All domain endpoints import from here.  This file is the single source of
truth for:
  - Extracting the authenticated user from the JWT.
  - Resolving the canonical koperasi_id (tenant) for the caller.
  - Role-based access control (RBAC) guards.
  - A helper that asserts a tenant is present (for endpoints that REQUIRE one).

Tenant resolution rules (from CLAUDE.md §3.2 / §3.3):
  - manager / admin  → users.koperasi_id  (non-null; 403 if null)
  - farmer           → farmers.koperasi_id (query farmers by user_id)
  - distributor / financing_partner / platform_admin → None (cross-tenant)
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_access_token
from app.db.engine import get_session
from app.models.enums import UserRole
from app.models.users import Farmer, User

logger = logging.getLogger(__name__)

# tokenUrl must match the login endpoint path so Swagger "Authorize" resolves it.
_oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login/form")

# ---------------------------------------------------------------------------
# CurrentUser context object
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CurrentUser:
    """
    Lightweight context object injected into route handlers via Depends.

    Attributes:
        user_id      — PK of the users row.
        role         — Validated UserRole enum member.
        koperasi_id  — Resolved tenant:
                         * int  → for manager/admin (from users) or farmer (from farmers).
                         * None → for distributor / financing_partner / platform_admin.
        email        — User's email address; may be None for phone-only accounts.
    """

    user_id: int
    role: UserRole
    koperasi_id: int | None
    email: str | None


# ---------------------------------------------------------------------------
# Core dependency: get_current_user
# ---------------------------------------------------------------------------


async def get_current_user(
    token: str = Depends(_oauth2_scheme),
    session: AsyncSession = Depends(get_session),
) -> CurrentUser:
    """
    FastAPI dependency that:
      1. Decodes + validates the Bearer JWT.
      2. Loads the User row from the DB.
      3. Resolves the canonical koperasi_id for the caller's role.

    Raises:
        HTTP 401 — missing/invalid/expired token, unknown user.
        HTTP 403 — manager/admin without a koperasi_id on their users row.
    """
    _401 = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    # --- 1. Decode token ---
    try:
        payload = decode_access_token(token)
    except JWTError:
        raise _401
    except ValueError:
        raise _401

    sub = payload.get("sub")
    if not sub:
        raise _401

    try:
        user_id = int(sub)
    except (TypeError, ValueError):
        raise _401

    # --- 2. Load user from DB ---
    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise _401
    if user.status != "active":
        raise _401

    # --- 3. Resolve tenant ---
    role: UserRole = user.role
    koperasi_id: int | None

    if role in (UserRole.manager, UserRole.admin):
        if user.koperasi_id is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Manager/admin account has no koperasi assigned — contact platform admin.",
            )
        koperasi_id = user.koperasi_id

    elif role == UserRole.farmer:
        # Canonical tenant lives on farmers.koperasi_id, NOT users.koperasi_id
        farmer_result = await session.execute(
            select(Farmer).where(Farmer.user_id == user_id)
        )
        farmer = farmer_result.scalar_one_or_none()
        if farmer is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Farmer profile not found for this user.",
            )
        koperasi_id = farmer.koperasi_id

    else:
        # distributor / financing_partner / platform_admin — cross-tenant
        koperasi_id = None

    return CurrentUser(
        user_id=user_id,
        role=role,
        koperasi_id=koperasi_id,
        email=user.email,
    )


# ---------------------------------------------------------------------------
# RBAC dependency factory
# ---------------------------------------------------------------------------


def require_role(*roles: UserRole):
    """
    FastAPI dependency factory for role-based access control.

    Usage:
        @router.get("/admin-only")
        async def endpoint(
            current_user: CurrentUser = Depends(require_role(UserRole.admin)),
        ):
            ...

    Raises:
        HTTP 403 — if the authenticated user's role is not in *roles*.
    """

    async def _check(
        current_user: CurrentUser = Depends(get_current_user),
    ) -> CurrentUser:
        if current_user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Required role(s): {[r.value for r in roles]}",
            )
        return current_user

    # Give the inner dependency a descriptive name for FastAPI's dependency graph.
    _check.__name__ = f"require_role({'_'.join(r.value for r in roles)})"
    return _check


# ---------------------------------------------------------------------------
# Tenant assertion helper
# ---------------------------------------------------------------------------


def get_tenant_id(current_user: CurrentUser) -> int:
    """
    Assert that the caller has a resolved tenant (koperasi_id is not None).

    Use this in endpoints that MUST be scoped to a single koperasi (e.g. fund
    management, loan admin).  Cross-tenant roles (distributor, platform_admin,
    financing_partner) will receive HTTP 403.

    Args:
        current_user: injected via Depends(get_current_user) or require_role(...).

    Returns:
        koperasi_id (int) — always non-None.

    Raises:
        HTTP 403 — if current_user.koperasi_id is None.
    """
    if current_user.koperasi_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This endpoint requires a tenant-scoped account (manager, admin, or farmer).",
        )
    return current_user.koperasi_id
