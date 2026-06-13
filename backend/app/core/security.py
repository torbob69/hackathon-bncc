"""
JWT and password hashing utilities.

- Password hashing: passlib CryptContext(bcrypt)
- JWT: python-jose (HS256 by default)

bcrypt silently truncates passwords longer than 72 bytes.  We SHA-256 the
password first (produces 32 bytes hex — always under the limit) so that long
passwords are not silently equivalent to their first-72-byte prefix.
"""
from __future__ import annotations

import hashlib
import logging
from datetime import UTC, datetime, timedelta

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings

logger = logging.getLogger(__name__)

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _pre_hash(plain: str) -> str:
    """
    bcrypt truncates at 72 bytes.  Pre-hashing with SHA-256 ensures every
    character of the user's password contributes to the stored hash.
    """
    return hashlib.sha256(plain.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Public password API
# ---------------------------------------------------------------------------

def hash_password(plain: str) -> str:
    """Return a bcrypt hash of *plain*."""
    return _pwd_context.hash(_pre_hash(plain))


def verify_password(plain: str, hashed: str) -> bool:
    """Return True if *plain* matches *hashed*."""
    return _pwd_context.verify(_pre_hash(plain), hashed)


# ---------------------------------------------------------------------------
# Public JWT API
# ---------------------------------------------------------------------------

def create_access_token(
    user_id: int,
    role: str,
    koperasi_id: int | None,
) -> str:
    """
    Create a signed JWT.

    Payload keys:
        sub          — str(user_id)
        role         — UserRole value string
        koperasi_id  — int or None
        iat          — issued-at (UTC epoch)
        exp          — expiry (UTC epoch)
    """
    now = datetime.now(UTC)
    expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    payload: dict = {
        "sub": str(user_id),
        "role": role,
        "koperasi_id": koperasi_id,
        "iat": now,
        "exp": expire,
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> dict:
    """
    Decode and validate a JWT.

    Raises:
        ValueError  — if the token is missing required claims or structurally bad.
        jose.ExpiredSignatureError  — propagated so callers can distinguish expiry.
        jose.JWTError  — for any other invalid-signature / malformed-token case.
    """
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET,
            algorithms=[settings.JWT_ALGORITHM],
        )
    except JWTError:
        raise  # let the dep layer translate to HTTP 401

    if "sub" not in payload:
        raise ValueError("JWT payload missing 'sub' claim")
    return payload
