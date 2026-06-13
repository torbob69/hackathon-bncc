"""
Shared append-only audit log writer.

Design rules (CLAUDE.md §3.8 / Phase 15):
  - audit_log is INSERT/SELECT only.  Never UPDATE or DELETE.
  - This function does NOT commit — the caller owns the transaction.
  - Flush after insert so the returned AuditLog has an id populated.
  - Serialize Decimal/datetime values to str before storing in JSON columns
    (PostgreSQL JSON doesn't have a Decimal type and SQLAlchemy would error).

Usage:
    from app.services.audit import write_audit

    entry = await write_audit(
        session,
        actor_user_id=current_user.user_id,
        koperasi_id=current_user.koperasi_id,
        action="farmer.approved",
        entity_type="farmers",
        entity_id=farmer.user_id,
        after={"status": "active"},
        ip=request.client.host if request.client else None,
    )
    # then commit in the calling service/route
"""
from __future__ import annotations

import logging
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditLog

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# JSON-safe serialization
# ---------------------------------------------------------------------------


def _json_safe(obj: dict | None) -> dict | None:
    """
    Recursively convert dict values that are not JSON-serialisable
    (Decimal, datetime, date) to str so they can be stored in a JSON column.

    Returns None if *obj* is None.
    """
    if obj is None:
        return None
    return _convert(obj)  # type: ignore[return-value]


def _convert(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _convert(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_convert(i) for i in value]
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return value


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def write_audit(
    session: AsyncSession,
    *,
    actor_user_id: int | None,
    koperasi_id: int | None,
    action: str,
    entity_type: str,
    entity_id: int | None = None,
    before: dict | None = None,
    after: dict | None = None,
    ip: str | None = None,
) -> AuditLog:
    """
    Append one row to audit_log inside the caller's transaction.

    Parameters:
        session        — The active AsyncSession (caller owns begin/commit).
        actor_user_id  — User performing the action; None for system actions.
        koperasi_id    — Tenant scope; None for platform-level actions.
        action         — Short action label, e.g. "farmer.approved",
                         "loan.disbursed", "harvest.confirmed".
        entity_type    — Table/domain name, e.g. "farmers", "loans".
        entity_id      — PK of the affected row, if applicable.
        before         — Snapshot of the entity BEFORE the change (optional).
                         Any Decimal/datetime values are auto-converted to str.
        after          — Snapshot of the entity AFTER the change (optional).
        ip             — Caller IP address for the audit trail.

    Returns:
        The flushed (but not committed) AuditLog ORM instance.
        The .id attribute is populated after flush.

    Note:
        This function intentionally does NOT call session.commit().  The
        calling service/route is responsible for committing (or rolling back).
        This ensures the audit entry and the business mutation land in the same
        database transaction.
    """
    entry = AuditLog(
        koperasi_id=koperasi_id,
        actor_user_id=actor_user_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        before_json=_json_safe(before),
        after_json=_json_safe(after),
        ip=ip,
    )
    session.add(entry)
    await session.flush()  # populates entry.id without committing

    logger.debug(
        "audit: action=%s entity=%s id=%s actor=%s koperasi=%s",
        action,
        entity_type,
        entity_id,
        actor_user_id,
        koperasi_id,
    )
    return entry
