"""
Farmer-facing loan router.

Prefix:  /loans
Tags:    loans
Auth:    require_role(UserRole.farmer) — all endpoints

Endpoints:
  POST  /loans    — farmer applies for a new loan
  GET   /loans    — farmer views their own loans

Tenant scoping:
  A farmer's canonical koperasi_id is resolved from farmers.koperasi_id via
  get_current_user in deps.py (not users.koperasi_id).  The CurrentUser object
  injected by require_role(UserRole.farmer) already carries the correct
  koperasi_id for the farmer.

  farmer_id is current_user.user_id (the farmer's users.id == farmers.user_id PK).

  get_tenant_id is used to assert the koperasi_id is not None before any DB
  operation.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import CurrentUser, get_tenant_id, require_role
from app.db.engine import get_session
from app.models.enums import UserRole
from app.schemas.loans import LoanApplyRequest, LoanOut
from app.services.loans import apply_loan, list_loans

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/loans", tags=["loans"])


# ---------------------------------------------------------------------------
# POST /loans — apply for a loan
# ---------------------------------------------------------------------------


@router.post("", response_model=LoanOut, status_code=status.HTTP_201_CREATED)
async def apply_for_loan(
    body: LoanApplyRequest,
    current_user: CurrentUser = Depends(require_role(UserRole.farmer)),
    session: AsyncSession = Depends(get_session),
) -> LoanOut:
    """
    Farmer submits a loan application.

    The farmer must be an active member of their koperasi (KSP basis).
    The loan is created in 'pending' status awaiting admin review.

    Returns the created loan.
    """
    koperasi_id = get_tenant_id(current_user)
    farmer_id = current_user.user_id  # farmers.user_id == users.id

    async with session.begin():
        # apply_loan raises HTTPException directly if farmer is inactive
        loan = await apply_loan(
            session,
            koperasi_id=koperasi_id,
            farmer_id=farmer_id,
            principal=body.principal,
            purpose=body.purpose,
            installment_months=body.installment_months,
            interest_rate=body.interest_rate,
        )

    logger.info(
        "loan.apply: farmer=%d koperasi=%d loan_id=%d principal=%s",
        farmer_id,
        koperasi_id,
        loan.id,
        body.principal,
    )
    return LoanOut.model_validate(loan)


# ---------------------------------------------------------------------------
# GET /loans — list farmer's own loans
# ---------------------------------------------------------------------------


@router.get("", response_model=list[LoanOut])
async def list_my_loans(
    current_user: CurrentUser = Depends(require_role(UserRole.farmer)),
    session: AsyncSession = Depends(get_session),
) -> list[LoanOut]:
    """
    Return all loans belonging to the authenticated farmer within their koperasi.

    Tenant-scoped: only loans where koperasi_id matches and farmer_id matches
    the current user are returned.
    """
    koperasi_id = get_tenant_id(current_user)
    farmer_id = current_user.user_id

    loans = await list_loans(
        session,
        koperasi_id=koperasi_id,
        farmer_id=farmer_id,
    )
    return [LoanOut.model_validate(loan) for loan in loans]
