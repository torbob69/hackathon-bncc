"""
JWT and password hashing utilities.

- Password hashing: the `bcrypt` library directly (passlib is avoided — its
  1.7.4 release runs an internal self-test that crashes against bcrypt >= 4.1).
- JWT: python-jose (HS256 by default)

bcrypt truncates passwords longer than 72 bytes.  We SHA-256 the password first
(produces 64 hex chars — always under the limit) so that long passwords are not
silently equivalent to their first-72-byte prefix.
"""
from __future__ import annotations

import hashlib
import logging
from datetime import UTC, datetime, timedelta

import bcrypt
from jose import JWTError, jwt

from app.core.config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _pre_hash(plain: str) -> bytes:
    """
    bcrypt truncates at 72 bytes.  Pre-hashing with SHA-256 ensures every
    character of the user's password contributes to the stored hash.  Returns
    the 64-char hex digest as ASCII bytes (always < 72 bytes).
    """
    return hashlib.sha256(plain.encode("utf-8")).hexdigest().encode("ascii")


# ---------------------------------------------------------------------------
# Public password API
# ---------------------------------------------------------------------------

def hash_password(plain: str) -> str:
    """Return a bcrypt hash of *plain* (utf-8 str, safe to store in a CHAR col)."""
    return bcrypt.hashpw(_pre_hash(plain), bcrypt.gensalt()).decode("ascii")


def verify_password(plain: str, hashed: str | None) -> bool:
    """Return True if *plain* matches the stored bcrypt *hashed*."""
    if hashed is None:
        return False
    try:
        return bcrypt.checkpw(_pre_hash(plain), hashed.encode("ascii"))
    except (ValueError, TypeError):
        # malformed/empty stored hash — treat as a non-match rather than raising
        return False


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
