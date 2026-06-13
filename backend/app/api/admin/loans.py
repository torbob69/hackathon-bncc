"""
Admin loan management router.

Prefix:  /admin/loans
Tags:    admin:loans
Auth:    require_role(UserRole.admin) — all endpoints

Endpoints:
  GET    /admin/loans              — list all loans for the koperasi (optional ?status= filter)
  GET    /admin/loans/{loan_id}    — get loan detail with installments + latest credit score
  POST   /admin/loans/{loan_id}/approve  — approve and disburse a pending loan
  POST   /admin/loans/{loan_id}/reject   — reject a pending loan (body: RejectRequest)

Tenant scoping:
  The admin's koperasi_id is resolved from their JWT via get_tenant_id(current_user).
  Every query is scoped to that koperasi — cross-tenant access is impossible.

Error mapping:
  LoanNotFound        → 404
  LoanStateError      → 409 (wrong status for requested transition)
  ExceedsCreditLimit  → 422
  InsufficientFunds   → 422
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import CurrentUser, get_tenant_id, require_role
from app.db.engine import get_session
from app.models.enums import LoanStatus, UserRole
from app.schemas.loans import LoanApplyRequest, LoanDetailOut, LoanOut, RejectRequest
from app.services.ledger import InsufficientFunds, PoolInvariantViolation
from app.services.loans import (
    ExceedsCreditLimit,
    LoanNotFound,
    LoanStateError,
    approve_loan,
    get_loan,
    list_loans,
    reject_loan,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/loans", tags=["admin:loans"])


# ---------------------------------------------------------------------------
# GET /admin/loans
# ---------------------------------------------------------------------------


@router.get("", response_model=list[LoanOut])
async def list_loans_admin(
    status: Optional[LoanStatus] = Query(
        None,
        description="Filter by loan status (pending, active, past_due, paid, rejected, seized).",
    ),
    current_user: CurrentUser = Depends(require_role(UserRole.admin)),
    session: AsyncSession = Depends(get_session),
) -> list[LoanOut]:
    """
    List all loans for the admin's koperasi.

    Optional query parameter ?status= narrows the results.
    Returns newest-first.
    """
    koperasi_id = get_tenant_id(current_user)
    loans = await list_loans(session, koperasi_id=koperasi_id, status=status)
    return [LoanOut.model_validate(loan) for loan in loans]


# ---------------------------------------------------------------------------
# GET /admin/loans/{loan_id}
# ---------------------------------------------------------------------------


@router.get("/{loan_id}", response_model=LoanDetailOut)
async def get_loan_admin(
    loan_id: int,
    current_user: CurrentUser = Depends(require_role(UserRole.admin)),
    session: AsyncSession = Depends(get_session),
) -> LoanDetailOut:
    """
    Get full loan detail including installment schedule and latest credit score.
    """
    koperasi_id = get_tenant_id(current_user)
    try:
        loan, installments, credit_score = await get_loan(
            session, koperasi_id=koperasi_id, loan_id=loan_id
        )
    except LoanNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    from app.schemas.loans import CreditScoreOut, InstallmentOut

    return LoanDetailOut(
        **LoanOut.model_validate(loan).model_dump(),
        installments=[InstallmentOut.model_validate(i) for i in installments],
        latest_credit_score=(
            CreditScoreOut.model_validate(credit_score) if credit_score else None
        ),
    )


# ---------------------------------------------------------------------------
# POST /admin/loans/{loan_id}/approve
# ---------------------------------------------------------------------------


@router.post("/{loan_id}/approve", response_model=LoanOut)
async def approve_loan_admin(
    loan_id: int,
    current_user: CurrentUser = Depends(require_role(UserRole.admin)),
    session: AsyncSession = Depends(get_session),
) -> LoanOut:
    """
    Approve and disburse a pending loan.

    Atomically:
      - Computes credit score and checks principal <= limit.
      - Debits the Loan Pool (APBN-funded only) via SELECT FOR UPDATE.
      - Calls the payment provider to disburse funds.
      - Generates the installment schedule.
      - Writes audit and status history.

    HTTP 409 if the loan is not in 'pending' status.
    HTTP 422 if principal exceeds the credit limit or the Loan Pool is insufficient.
    """
    koperasi_id = get_tenant_id(current_user)

    async with session.begin():
        try:
            loan = await approve_loan(
                session,
                koperasi_id=koperasi_id,
                loan_id=loan_id,
                admin_user_id=current_user.user_id,
            )
        except LoanNotFound as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
            ) from exc
        except LoanStateError as exc:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail=str(exc)
            ) from exc
        except ExceedsCreditLimit as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    f"Principal {exc.principal} exceeds the farmer's credit limit "
                    f"{exc.limit} at time of scoring."
                ),
            ) from exc
        except InsufficientFunds as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    f"Insufficient funds in the Loan Pool: "
                    f"available={exc.available}, requested={exc.requested}."
                ),
            ) from exc
        except PoolInvariantViolation as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=str(exc),
            ) from exc

    return LoanOut.model_validate(loan)


# ---------------------------------------------------------------------------
# POST /admin/loans/{loan_id}/reject
# ---------------------------------------------------------------------------


@router.post("/{loan_id}/reject", response_model=LoanOut)
async def reject_loan_admin(
    loan_id: int,
    body: RejectRequest,
    current_user: CurrentUser = Depends(require_role(UserRole.admin)),
    session: AsyncSession = Depends(get_session),
) -> LoanOut:
    """
    Reject a pending loan application.

    HTTP 409 if the loan is not in 'pending' status.
    """
    koperasi_id = get_tenant_id(current_user)

    async with session.begin():
        try:
            loan = await reject_loan(
                session,
                koperasi_id=koperasi_id,
                loan_id=loan_id,
                admin_user_id=current_user.user_id,
                reason=body.reason,
            )
        except LoanNotFound as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
            ) from exc
        except LoanStateError as exc:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail=str(exc)
            ) from exc

    return LoanOut.model_validate(loan)
