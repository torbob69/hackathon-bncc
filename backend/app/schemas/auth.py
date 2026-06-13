"""
Pydantic v2 schemas for authentication endpoints.
"""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.models.enums import UserRole


class SignupRequest(BaseModel):
    """
    Used for POST /auth/signup.

    koperasi_id is required when role is manager or admin.
    For demo/seed purposes any role may be created directly.
    """

    name: str = Field(..., min_length=1, max_length=255)
    email: EmailStr
    password: str = Field(..., min_length=8, description="Minimum 8 characters")
    role: UserRole
    koperasi_id: int | None = None
    phone: str | None = Field(default=None, max_length=20)

    @field_validator("koperasi_id")
    @classmethod
    def _validate_koperasi_for_role(cls, v: int | None, info) -> int | None:
        # field_validator runs after individual field parsing; values are in info.data
        role = info.data.get("role")
        if role in (UserRole.manager, UserRole.admin) and v is None:
            raise ValueError("koperasi_id is required for manager and admin roles")
        return v


class LoginRequest(BaseModel):
    """Used for POST /auth/login (JSON body variant)."""

    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    """Returned after successful login."""

    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    """
    Safe user representation returned by signup, login (/me), etc.
    Never includes password_hash.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    email: str
    role: UserRole
    koperasi_id: int | None
    status: str
