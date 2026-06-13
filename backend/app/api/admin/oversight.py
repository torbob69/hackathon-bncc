"""
Admin — Audit Log Viewer + Dashboard Metrics endpoints.

Router prefix : /admin
Tags          : ["admin:oversight"]
Auth          : every endpoint requires UserRole.admin (via Depends(require_role))
Tenant        : resolved from the admin's JWT via get_tenant_id(current_user)

Endpoints:
  GET /admin/audit-log   — paginated, filterable, tenant-scoped audit log (read-only)
  GET /admin/dashboard   — aggregated KPI dashboard for the admin's koperasi

The audit_log table is append-only (CLAUDE.md §3.8 / Phase 15).  This router
only reads it; writes happen exclusively through app.services.audit.write_audit.
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, EmailStr, model_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.deps import CurrentUser, get_tenant_id, require_role
from app.db.engine import get_session
from app.models.audit import AuditLog
from app.models.enums import UserRole
from app.schemas.oversight import AuditLogOut, DashboardOut
from app.services import notifier
from app.services.dashboard import compute_dashboard

router = APIRouter(prefix="/admin", tags=["admin:oversight"])


# ---------------------------------------------------------------------------
# POST /admin/test-notification
# ---------------------------------------------------------------------------


class TestNotificationRequest(BaseModel):
    email: EmailStr | None = None
    phone: str | None = None

    @model_validator(mode="after")
    def _at_least_one(self) -> "TestNotificationRequest":
        if self.email is None and self.phone is None:
            raise ValueError("Provide at least one of email or phone.")
        return self


@router.post(
    "/test-notification",
    summary="Test Fonnte (WhatsApp) and Gmail SMTP delivery",
)
async def test_notification(
    body: TestNotificationRequest,
) -> dict:
    """
    Sends a real test message and returns per-channel success/error details.
    - `email` → tests Gmail SMTP.
    - `phone` → tests Fonnte WhatsApp (e.g. 08123456789).
    """
    import asyncio

    test_url = f"{settings.FRONTEND_URL}/activate?token=TEST_TOKEN_DO_NOT_USE"
    results: dict = {}

    async def _try_email(to_email: str) -> dict:
        try:
            await notifier._send_email_raising(to_email, test_url, "Test User")
            return {"ok": True}
        except Exception as exc:
            return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}

    async def _try_whatsapp(to_phone: str) -> dict:
        try:
            await notifier.send_activation_whatsapp(to_phone, test_url, "Test User")
            return {"ok": True}
        except Exception as exc:
            return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}

    tasks = {}
    if body.email:
        tasks["email"] = _try_email(str(body.email))
    if body.phone:
        tasks["whatsapp"] = _try_whatsapp(body.phone)

    gathered = await asyncio.gather(*tasks.values(), return_exceptions=False)
    results = dict(zip(tasks.keys(), gathered))

    return {
        "ok": all(r["ok"] for r in results.values()),
        "results": results,
        "config": {
            "smtp_configured": bool(settings.SMTP_USER),
            "fonnte_configured": bool(settings.FONNTE_TOKEN),
        },
    }


# ---------------------------------------------------------------------------
# GET /admin/audit-log
# ---------------------------------------------------------------------------


@router.get(
    "/audit-log",
    response_model=list[AuditLogOut],
    summary="List audit log entries (admin)",
)
async def list_audit_log(
    entity_type: Optional[str] = Query(
        default=None,
        description="Filter by entity type, e.g. 'farmers', 'loans', 'harvest_intakes'.",
    ),
    action: Optional[str] = Query(
        default=None,
        description="Filter by action label, e.g. 'farmer.approved', 'loan.disbursed'.",
    ),
    limit: int = Query(
        default=50,
        ge=1,
        le=200,
        description="Maximum number of records to return (1–200). Default: 50.",
    ),
    offset: int = Query(
        default=0,
        ge=0,
        description="Number of records to skip for pagination. Default: 0.",
    ),
    current_user: CurrentUser = Depends(require_role(UserRole.admin)),
    session: AsyncSession = Depends(get_session),
) -> list[AuditLogOut]:
    """
    Return audit log entries for the admin's koperasi, most-recent first.

    Filters:
    - `entity_type` — exact-match filter on the entity_type column
      (e.g. `farmers`, `loans`, `harvest_intakes`).
    - `action` — exact-match filter on the action column
      (e.g. `farmer.approved`, `loan.disbursed`).

    The result is tenant-scoped: only rows whose `koperasi_id` matches the
    authenticated admin's koperasi are returned.

    Pagination:
    - `limit` — page size, max 200.
    - `offset` — records to skip.
    """
    koperasi_id = get_tenant_id(current_user)

    stmt = (
        select(AuditLog)
        .where(AuditLog.koperasi_id == koperasi_id)
        .order_by(AuditLog.created_at.desc())
        .limit(limit)
        .offset(offset)
    )

    if entity_type is not None:
        stmt = stmt.where(AuditLog.entity_type == entity_type)

    if action is not None:
        stmt = stmt.where(AuditLog.action == action)

    result = await session.execute(stmt)
    rows = result.scalars().all()

    return [AuditLogOut.model_validate(row) for row in rows]


# ---------------------------------------------------------------------------
# GET /admin/dashboard
# ---------------------------------------------------------------------------


@router.get(
    "/dashboard",
    response_model=DashboardOut,
    summary="Admin KPI dashboard",
)
async def get_dashboard(
    current_user: CurrentUser = Depends(require_role(UserRole.admin)),
    session: AsyncSession = Depends(get_session),
) -> DashboardOut:
    """
    Return aggregated KPI metrics for the admin's koperasi.

    Metrics:
    - **gmv** — Gross Merchandise Value: sum of `orders.total` for paid/fulfilled orders.
    - **active_farmer_count** / **total_farmer_count** — farmer roster counts.
    - **active_farmer_rate** — fraction [0, 1] of active farmers vs total.
    - **loan_disbursement_volume** — sum of `loans.principal` for all disbursed loans.
    - **active_loan_count** — loans in `active` or `past_due` status.
    - **npl_count** — non-performing loans: `past_due` or `seized`.
    - **npl_rate** — fraction [0, 1] of NPL loans within the at-risk portfolio.
    - **marginal_profit_pool_balance** / **loan_pool_balance** — live fund balances.

    All money values are returned as Decimal strings in JSON.
    Rates are fractions in [0, 1] (e.g. 0.15 = 15%).
    """
    koperasi_id = get_tenant_id(current_user)
    return await compute_dashboard(session, koperasi_id=koperasi_id)
