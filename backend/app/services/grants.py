"""
Data-share grant lifecycle service.

CLAUDE.md §3.8 / Phase 15 — controls which aggregate fields a financing partner
may see and for which date range within a given koperasi.

Public API:
    create_grant(session, *, koperasi_id, financing_partner_id, fields,
                 date_range_start, date_range_end, granted_by) -> DataShareGrant
    list_grants(session, *, koperasi_id) -> list[DataShareGrant]
    revoke_grant(session, *, koperasi_id, grant_id, actor_user_id) -> DataShareGrant

Exceptions:
    InvalidScope   — one or more requested fields are not in ALLOWED_REPORT_FIELDS.
    GrantNotFound  — the requested grant does not exist within the caller's tenant.

Design rules:
  - scope_json is stored as {"fields": [...]} — the service layer always validates
    each field name against ALLOWED_REPORT_FIELDS before persisting.
  - Tenant isolation: every query filters by koperasi_id; a cross-tenant grant_id
    raises GrantNotFound (same as if it doesn't exist, to avoid ID enumeration).
  - write_audit is called inside every mutating transaction; the caller (router)
    wraps the call in `async with session.begin():` so audit + grant land together.
  - This service NEVER commits; the router owns the transaction boundary.
"""
from __future__ import annotations

import logging
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import GrantStatus
from app.models.grants import DataShareGrant
from app.schemas.reports import ALLOWED_REPORT_FIELDS
from app.services.audit import write_audit

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class InvalidScope(ValueError):
    """Raised when a requested field name is not in ALLOWED_REPORT_FIELDS."""

    def __init__(self, bad_fields: list[str]) -> None:
        self.bad_fields = bad_fields
        super().__init__(
            f"Disallowed field(s) in scope: {bad_fields!r}. "
            f"Permitted: {sorted(ALLOWED_REPORT_FIELDS)}"
        )


class GrantNotFound(Exception):
    """Raised when a grant_id does not exist within the caller's koperasi."""

    pass


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _validate_fields(fields: list[str]) -> list[str]:
    """
    Validate that every requested field is in ALLOWED_REPORT_FIELDS.

    Returns the de-duplicated, sorted list of valid field names.
    Raises InvalidScope if any field name is not permitted.
    """
    bad = [f for f in fields if f not in ALLOWED_REPORT_FIELDS]
    if bad:
        raise InvalidScope(bad)
    # De-duplicate while preserving order, then return
    seen: set[str] = set()
    clean: list[str] = []
    for f in fields:
        if f not in seen:
            seen.add(f)
            clean.append(f)
    return clean


# ---------------------------------------------------------------------------
# create_grant
# ---------------------------------------------------------------------------


async def create_grant(
    session: AsyncSession,
    *,
    koperasi_id: int,
    financing_partner_id: int,
    fields: list[str],
    date_range_start: date,
    date_range_end: date,
    granted_by: int,
) -> DataShareGrant:
    """
    Create a new data-share grant for a financing partner.

    The caller (router) MUST wrap this in `async with session.begin():`.
    This function does not commit.

    Args:
        session               — Active AsyncSession (no active transaction needed;
                                caller owns `session.begin()`).
        koperasi_id           — Tenant; all grants are koperasi-scoped.
        financing_partner_id  — FK to financing_partners.id.
        fields                — List of aggregate field names to grant access to.
                                Validated against ALLOWED_REPORT_FIELDS.
        date_range_start      — Start of the reportable date range (inclusive).
        date_range_end        — End of the reportable date range (inclusive).
        granted_by            — user_id of the admin creating the grant.

    Returns:
        The flushed (not committed) DataShareGrant ORM instance.

    Raises:
        InvalidScope — if any field name is not in ALLOWED_REPORT_FIELDS.
    """
    validated_fields = _validate_fields(fields)

    grant = DataShareGrant(
        koperasi_id=koperasi_id,
        financing_partner_id=financing_partner_id,
        scope_json={"fields": validated_fields},
        date_range_start=date_range_start,
        date_range_end=date_range_end,
        status=GrantStatus.active,
        granted_by=granted_by,
    )
    session.add(grant)
    await session.flush()  # populates grant.id without committing

    await write_audit(
        session,
        actor_user_id=granted_by,
        koperasi_id=koperasi_id,
        action="grant_created",
        entity_type="data_share_grants",
        entity_id=grant.id,
        after={
            "financing_partner_id": financing_partner_id,
            "scope_json": grant.scope_json,
            "date_range_start": date_range_start.isoformat() if hasattr(date_range_start, "isoformat") else str(date_range_start),
            "date_range_end": date_range_end.isoformat() if hasattr(date_range_end, "isoformat") else str(date_range_end),
        },
    )

    logger.info(
        "grant_created: id=%d koperasi=%d partner=%d fields=%s actor=%d",
        grant.id,
        koperasi_id,
        financing_partner_id,
        validated_fields,
        granted_by,
    )
    return grant


# ---------------------------------------------------------------------------
# list_grants
# ---------------------------------------------------------------------------


async def list_grants(
    session: AsyncSession,
    *,
    koperasi_id: int,
) -> list[DataShareGrant]:
    """
    Return all data-share grants for *koperasi_id*, newest first.

    Tenant-scoped — never returns grants belonging to another koperasi.
    """
    result = await session.execute(
        select(DataShareGrant)
        .where(DataShareGrant.koperasi_id == koperasi_id)
        .order_by(DataShareGrant.created_at.desc())
    )
    return list(result.scalars().all())


# ---------------------------------------------------------------------------
# revoke_grant
# ---------------------------------------------------------------------------


async def revoke_grant(
    session: AsyncSession,
    *,
    koperasi_id: int,
    grant_id: int,
    actor_user_id: int,
) -> DataShareGrant:
    """
    Revoke an active data-share grant.

    The caller (router) MUST wrap this in `async with session.begin():`.
    This function does not commit.

    Args:
        session         — Active AsyncSession (no active transaction needed;
                          caller owns `session.begin()`).
        koperasi_id     — Caller's tenant; used to enforce tenant isolation.
        grant_id        — PK of the grant to revoke.
        actor_user_id   — user_id of the admin performing the revocation.

    Returns:
        The updated (flushed, not committed) DataShareGrant instance.

    Raises:
        GrantNotFound — if no grant with *grant_id* exists within *koperasi_id*
                        (covers both "does not exist" and "wrong tenant" cases).
    """
    result = await session.execute(
        select(DataShareGrant).where(
            DataShareGrant.id == grant_id,
            DataShareGrant.koperasi_id == koperasi_id,
        )
    )
    grant = result.scalar_one_or_none()
    if grant is None:
        raise GrantNotFound(f"Grant {grant_id} not found in koperasi {koperasi_id}")

    old_status = grant.status

    grant.status = GrantStatus.revoked
    await session.flush()

    await write_audit(
        session,
        actor_user_id=actor_user_id,
        koperasi_id=koperasi_id,
        action="grant_revoked",
        entity_type="data_share_grants",
        entity_id=grant.id,
        before={"status": old_status.value if hasattr(old_status, "value") else str(old_status)},
        after={"status": GrantStatus.revoked.value},
    )

    logger.info(
        "grant_revoked: id=%d koperasi=%d actor=%d",
        grant.id,
        koperasi_id,
        actor_user_id,
    )
    return grant
