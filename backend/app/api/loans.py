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
from app.schemas.loans import (
    CreditScoreOut,
    InstallmentOut,
    LoanApplyRequest,
    LoanDetailOut,
    LoanOut,
    RepayRequest,
)
from app.services.ledger import InsufficientFunds, PoolInvariantViolation
from app.services.loans import (
    LoanNotFound,
    LoanStateError,
    apply_loan,
    get_loan,
    list_loans,
    repay_installment,
)

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


# ---------------------------------------------------------------------------
# GET /loans/{loan_id} — farmer views their own loan detail
# ---------------------------------------------------------------------------


@router.get("/{loan_id}", response_model=LoanDetailOut)
async def get_my_loan(
    loan_id: int,
    current_user: CurrentUser = Depends(require_role(UserRole.farmer)),
    session: AsyncSession = Depends(get_session),
) -> LoanDetailOut:
    """
    Return full detail for one of the authenticated farmer's loans.

    Includes the installment schedule and the latest credit score snapshot.
    Returns 404 if the loan does not exist or belongs to a different farmer /
    koperasi.
    """
    koperasi_id = get_tenant_id(current_user)
    farmer_id = current_user.user_id

    try:
        loan, installments, credit_score = await get_loan(
            session, koperasi_id=koperasi_id, loan_id=loan_id
        )
    except LoanNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    # Farmer may only see their own loans
    if loan.farmer_id != farmer_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Loan not found.")

    return LoanDetailOut(
        **LoanOut.model_validate(loan).model_dump(),
        installments=[InstallmentOut.model_validate(i) for i in installments],
        latest_credit_score=(
            CreditScoreOut.model_validate(credit_score) if credit_score else None
        ),
    )


# ---------------------------------------------------------------------------
# POST /loans/{loan_id}/repay — farmer submits an installment repayment
# ---------------------------------------------------------------------------


@router.post("/{loan_id}/repay", response_model=LoanDetailOut)
async def repay_loan_installment(
    loan_id: int,
    body: RepayRequest,
    current_user: CurrentUser = Depends(require_role(UserRole.farmer)),
    session: AsyncSession = Depends(get_session),
) -> LoanDetailOut:
    """
    Farmer pays one installment on their loan.

    The specified installment must be in 'unpaid' or 'late' status.
    Amount defaults to the full remaining balance when omitted.
    Overpayment beyond the remaining balance is rejected with HTTP 409.

    The repayment CREDITS the Loan Pool (inbound money from the farmer).
    No payment-provider call is made; the ledger entry is the record.

    Returns updated full loan detail (installments + credit score).
    """
    koperasi_id = get_tenant_id(current_user)
    farmer_id = current_user.user_id

    async with session.begin():
        try:
            loan, _installment = await repay_installment(
                session,
                koperasi_id=koperasi_id,
                loan_id=loan_id,
                installment_id=body.installment_id,
                payer_user_id=farmer_id,
                amount=body.amount,
            )
        except LoanNotFound as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
            ) from exc
        except LoanStateError as exc:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail=str(exc)
            ) from exc
        except InsufficientFunds as exc:
            # A credit cannot fail due to insufficient funds, but map it defensively
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
            ) from exc
        except PoolInvariantViolation as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
            ) from exc

        # Farmer may only repay their own loans
        if loan.farmer_id != farmer_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Loan not found."
            )

    # Re-fetch full detail (installments may have changed status in this txn)
    loan, installments, credit_score = await get_loan(
        session, koperasi_id=koperasi_id, loan_id=loan_id
    )

    logger.info(
        "loan.repay: farmer=%d koperasi=%d loan_id=%d installment_id=%d",
        farmer_id,
        koperasi_id,
        loan_id,
        body.installment_id,
    )
    return LoanDetailOut(
        **LoanOut.model_validate(loan).model_dump(),
        installments=[InstallmentOut.model_validate(i) for i in installments],
        latest_credit_score=(
            CreditScoreOut.model_validate(credit_score) if credit_score else None
        ),
    )
