from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from jose import JWTError, jwt

from app.core.config import settings

HARVEST_QR_TYPE = "harvest_intake"
PICKUP_QR_TYPE = "pickup"


class QRVerificationError(ValueError):
    pass


class InvalidQrToken(ValueError):
    """Raised when a generic signed QR payload is invalid, expired, or mistyped."""


def sign_qr_payload(
    *,
    payload_type: str,
    payload: dict[str, Any],
    expires_in_hours: int = 72,
) -> str:
    """Sign an arbitrary QR payload as a JWT (e.g. pickup tokens).

    The signature is the anti-fraud (asli/palsu) guarantee; `typ` binds the
    token to a single operation so a token signed for one flow can't be replayed
    in another.
    """
    now = datetime.now(UTC)
    body: dict[str, Any] = {
        "typ": payload_type,
        "iat": now,
        "exp": now + timedelta(hours=expires_in_hours),
        **payload,
    }
    return jwt.encode(body, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def verify_qr_payload(*, token: str, expected_type: str) -> dict[str, Any]:
    """Decode and validate a generic signed QR payload, asserting its `typ`."""
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET,
            algorithms=[settings.JWT_ALGORITHM],
        )
    except JWTError as exc:
        raise InvalidQrToken("QR token is invalid or expired.") from exc

    if payload.get("typ") != expected_type:
        raise InvalidQrToken("QR token type is not valid for this operation.")
    return payload


def sign_harvest_intake_qr(
    *,
    intake_id: int,
    koperasi_id: int,
    farmer_id: int,
    commodity_id: int,
    weight_kg: Decimal,
    expires_in_hours: int = 24,
) -> str:
    now = datetime.now(UTC)
    payload = {
        "typ": HARVEST_QR_TYPE,
        "sub": str(intake_id),
        "koperasi_id": koperasi_id,
        "farmer_id": farmer_id,
        "commodity_id": commodity_id,
        "weight_kg": str(weight_kg),
        "iat": now,
        "exp": now + timedelta(hours=expires_in_hours),
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def verify_qr_token(token: str, *, expected_type: str = HARVEST_QR_TYPE) -> dict[str, Any]:
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET,
            algorithms=[settings.JWT_ALGORITHM],
        )
    except JWTError as exc:
        raise QRVerificationError("QR token is invalid or expired.") from exc

    if payload.get("typ") != expected_type:
        raise QRVerificationError("QR token type is not valid for this operation.")
    if "sub" not in payload:
        raise QRVerificationError("QR token is missing an intake reference.")
    return payload
