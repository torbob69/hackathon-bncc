"""
Reports router — portfolio reporting, data-share grants, and anomaly detection.

Router prefix  : /reports   (set by orchestrator in main.py — not here)
Tags           : ["reports"]
Router var     : router

Endpoints
---------
POST  /reports/grants                      — Admin creates a data-share grant
GET   /reports/grants                      — Admin lists grants for their koperasi
POST  /reports/grants/{grant_id}/revoke    — Admin revokes a grant
GET   /reports/portfolio                   — Financing partner reads portfolio report
GET   /reports/anomalies                   — Admin reads anomaly detection results

Auth / tenant rules (CLAUDE.md §3.8 / §8):
  - /grants* and /anomalies : require_role(UserRole.admin); koperasi_id from get_tenant_id.
  - /portfolio              : require_role(UserRole.financing_partner); resolves
                              JWT.user_id → FinancingPartner → active grants.
                              Returns 403 if the caller is not a registered financing partner.
  - Portfolio NEVER exceeds grant scope: only fields in scope_json["fields"] are returned,
    filtered to the grant's date range.  See services/reports.py for enforcement.

Transaction discipline:
  - Grant create/revoke use `async with session.begin():` so the grant write and
    audit entry land in one transaction.
  - Read endpoints (list_grants, portfolio, anomalies) do not open transactions.

Error mapping:
  - InvalidScope   → HTTP 422
  - GrantNotFound  → HTTP 404
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import CurrentUser, get_tenant_id, require_role
from app.db.engine import get_session
from app.models.enums import UserRole
from app.schemas.reports import (
    AnomalyOut,
    GrantCreate,
    GrantOut,
    PortfolioReportOut,
)
from app.services.anomaly import detect_anomalies
from app.services.grants import GrantNotFound, InvalidScope, create_grant, list_grants, revoke_grant
from app.services.reports import portfolio_for_partner, resolve_partner

logger = logging.getLogger(__name__)

router = APIRouter(tags=["reports"])

# ---------------------------------------------------------------------------
# Shared admin dependency (cached at module load — zero cost)
# ---------------------------------------------------------------------------

_admin_dep = require_role(UserRole.admin)
_partner_dep = require_role(UserRole.financing_partner)


# ---------------------------------------------------------------------------
# POST /reports/grants
# ---------------------------------------------------------------------------


@router.post(
    "/grants",
    response_model=GrantOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create a data-share grant for a financing partner (admin)",
)
async def create_grant_endpoint(
    body: GrantCreate,
    current_user: CurrentUser = Depends(_admin_dep),
    session: AsyncSession = Depends(get_session),
) -> GrantOut:
    """
    Create a new data-share grant authorising a financing partner to see
    a specific set of aggregate metrics for this koperasi within a date range.

    Only field names in the platform allow-list (ALLOWED_REPORT_FIELDS) are
    accepted.  Any disallowed field name results in HTTP 422.

    The grant and audit entry are written in one atomic transaction.
    """
    koperasi_id = get_tenant_id(current_user)

    try:
        async with session.begin():
            grant = await create_grant(
                session,
                koperasi_id=koperasi_id,
                financing_partner_id=body.financing_partner_id,
                fields=body.fields,
                date_range_start=body.date_range_start,
                date_range_end=body.date_range_end,
                granted_by=current_user.user_id,
            )
    except InvalidScope as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    logger.info(
        "create_grant: id=%d koperasi=%d partner=%d actor=%d",
        grant.id,
        koperasi_id,
        body.financing_partner_id,
        current_user.user_id,
    )
    return GrantOut.model_validate(grant)


# ---------------------------------------------------------------------------
# GET /reports/grants
# ---------------------------------------------------------------------------


@router.get(
    "/grants",
    response_model=list[GrantOut],
    summary="List data-share grants for the admin's koperasi",
)
async def list_grants_endpoint(
    current_user: CurrentUser = Depends(_admin_dep),
    session: AsyncSession = Depends(get_session),
) -> list[GrantOut]:
    """
    Return all data-share grants for the authenticated admin's koperasi,
    ordered newest first.  Both active and revoked grants are returned.

    Tenant-scoped — never returns grants from other koperasi.
    """
    koperasi_id = get_tenant_id(current_user)
    grants = await list_grants(session, koperasi_id=koperasi_id)
    return [GrantOut.model_validate(g) for g in grants]


# ---------------------------------------------------------------------------
# POST /reports/grants/{grant_id}/revoke
# ---------------------------------------------------------------------------


@router.post(
    "/grants/{grant_id}/revoke",
    response_model=GrantOut,
    summary="Revoke a data-share grant (admin)",
)
async def revoke_grant_endpoint(
    grant_id: int,
    current_user: CurrentUser = Depends(_admin_dep),
    session: AsyncSession = Depends(get_session),
) -> GrantOut:
    """
    Revoke a data-share grant so the financing partner can no longer access
    this koperasi's portfolio data.

    The revocation and audit entry are written in one atomic transaction.
    Returns the updated grant (status = revoked).

    Raises HTTP 404 if the grant does not exist within the caller's koperasi.
    """
    koperasi_id = get_tenant_id(current_user)

    try:
        async with session.begin():
            grant = await revoke_grant(
                session,
                koperasi_id=koperasi_id,
                grant_id=grant_id,
                actor_user_id=current_user.user_id,
            )
    except GrantNotFound as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    logger.info(
        "revoke_grant: id=%d koperasi=%d actor=%d",
        grant.id,
        koperasi_id,
        current_user.user_id,
    )
    return GrantOut.model_validate(grant)


# ---------------------------------------------------------------------------
# GET /reports/portfolio
# ---------------------------------------------------------------------------


@router.get(
    "/portfolio",
    response_model=list[PortfolioReportOut],
    summary="Portfolio report for the authenticated financing partner",
)
async def get_portfolio(
    current_user: CurrentUser = Depends(_partner_dep),
    session: AsyncSession = Depends(get_session),
) -> list[PortfolioReportOut]:
    """
    Return portfolio aggregate metrics for all koperasi that have granted
    this financing partner access.

    Auth chain (CLAUDE.md §8):
        JWT.user_id → financing_partners.user_id → data_share_grants (active only)

    For each active grant, the response contains ONLY the fields listed in
    scope_json["fields"], filtered to the grant's date range.  Raw PII and
    fields not in the grant scope are never included.

    Returns an empty list if no active grants exist for this partner.
    Returns HTTP 403 if the caller is not a registered financing partner.
    """
    partner = await resolve_partner(session, user_id=current_user.user_id)
    if partner is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account is not registered as a financing partner.",
        )

    reports = await portfolio_for_partner(session, partner=partner)

    logger.info(
        "get_portfolio: partner_id=%d user_id=%d report_count=%d",
        partner.id,
        current_user.user_id,
        len(reports),
    )
    return reports


# ---------------------------------------------------------------------------
# GET /reports/anomalies
# ---------------------------------------------------------------------------


@router.get(
    "/anomalies",
    response_model=list[AnomalyOut],
    summary="Anomaly / fraud detection findings for the admin's koperasi",
)
async def get_anomalies(
    current_user: CurrentUser = Depends(_admin_dep),
    session: AsyncSession = Depends(get_session),
) -> list[AnomalyOut]:
    """
    Run heuristic anomaly checks over ledger_entries and harvest_intakes for
    the authenticated admin's koperasi and return any suspicious findings.

    Heuristics:
    - **orphan_debit** — debit ledger entries with no reference_id (high).
    - **pihps_price_deviation** — confirmed intakes where price_per_kg deviates
      from the commodity's current PIHPS price (high).
    - **large_ledger_entry** — single debit > 5× median debit amount (medium).
    - **rapid_fire_confirms** — ≥3 confirms by the same manager in 5 min (medium).

    Results are sorted by created_at descending.  Read-only — no data is mutated.
    An empty list means no anomalies were detected.
    """
    koperasi_id = get_tenant_id(current_user)
    findings = await detect_anomalies(session, koperasi_id=koperasi_id)

    logger.info(
        "get_anomalies: koperasi=%d actor=%d found=%d",
        koperasi_id,
        current_user.user_id,
        len(findings),
    )
    return findings
