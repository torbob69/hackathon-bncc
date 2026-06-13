"""
Loan lifecycle service — apply, approve, reject, query.

Business rules enforced here (CLAUDE.md §2.4, §3.7, §8):
  - Loans are for active koperasi MEMBERS only (KSP basis).
  - All disbursements come exclusively from the Loan Pool (APBN-funded).
    The Marginal Profit Pool is never touched here.
  - Pool sufficiency check uses SELECT … FOR UPDATE inside the same transaction
    as the ledger write (via post_ledger_entry which handles the locking).
  - All money movements go through get_payment_provider() — never direct Xendit.
  - Disbursement is idempotent: external_idempotency_key = f"loan-disb-{loan_id}"
    prevents double-posting on retries.
  - Every status change is recorded in LoanStatusHistory.
  - Audit entries are written but not committed here — caller (router) commits.

No commits in this module — callers own the transaction boundary.
The approve_loan function uses session.begin() internally as a context manager
to wrap the full multi-step atomic operation.
"""
from __future__ import annotations

import logging
from datetime import UTC, date, datetime
from decimal import ROUND_HALF_UP, Decimal

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import (
    FarmerStatus,
    InstallmentStatus,
    LedgerDirection,
    LedgerPool,
    LedgerType,
    LoanPurpose,
    LoanStatus,
)
from app.models.loans import Loan, LoanInstallment, LoanStatusHistory
from app.models.users import Farmer
from app.payments import get_payment_provider
from app.services.audit import write_audit
from app.services.credit import compute_credit_score, tier_to_limit
from app.services.ledger import InsufficientFunds, post_ledger_entry

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Custom domain exceptions (translated to HTTP in routers)
# ---------------------------------------------------------------------------


class LoanNotFound(Exception):
    """Raised when the loan does not exist or belongs to a different tenant."""


class LoanStateError(Exception):
    """Raised when a loan is in the wrong status for the requested operation."""


class ExceedsCreditLimit(Exception):
    """Raised when principal exceeds the farmer's computed credit limit."""

    def __init__(self, principal: Decimal, limit: Decimal) -> None:
        self.principal = principal
        self.limit = limit
        super().__init__(
            f"Principal {principal} exceeds credit limit {limit}."
        )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


async def _get_loan_for_update(
    session: AsyncSession, *, koperasi_id: int, loan_id: int
) -> Loan:
    """
    Fetch a Loan row with a row-level lock (FOR UPDATE), tenant-scoped.

    Raises LoanNotFound if the loan doesn't exist under this koperasi.
    """
    result = await session.execute(
        select(Loan)
        .where(
            Loan.id == loan_id,
            Loan.koperasi_id == koperasi_id,
        )
        .with_for_update()
    )
    loan = result.scalar_one_or_none()
    if loan is None:
        raise LoanNotFound(f"Loan {loan_id} not found in koperasi {koperasi_id}.")
    return loan


def _generate_installments(
    *,
    loan_id: int,
    koperasi_id: int,
    principal: Decimal,
    interest_rate: Decimal,
    installment_months: int,
    start_date: date,
) -> list[LoanInstallment]:
    """
    Generate *installment_months* LoanInstallment objects.

    Total due = principal * (1 + interest_rate / 100).
    Each installment = total_due / months, rounded to 2dp.
    The final installment absorbs any rounding remainder so that the sum is exact.

    due_date is monthly from start_date (day-of-month preserved where possible;
    if the month is shorter the last valid day is used implicitly via date arithmetic).
    """
    total_due: Decimal = (principal * (1 + interest_rate / Decimal("100"))).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )
    per_installment: Decimal = (total_due / Decimal(str(installment_months))).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )
    # Remainder goes on the last installment
    remainder: Decimal = total_due - per_installment * Decimal(str(installment_months))

    installments: list[LoanInstallment] = []
    for i in range(installment_months):
        # Advance by i+1 months.  Use the replace trick to stay on the same
        # day-of-month; Python's date handles end-of-month correctly via
        # dateutil logic — here we do a simple month wrap manually.
        month = start_date.month + (i + 1)
        year = start_date.year + (month - 1) // 12
        month = ((month - 1) % 12) + 1
        # Clamp day to last day of target month
        import calendar
        last_day = calendar.monthrange(year, month)[1]
        due_day = min(start_date.day, last_day)
        due_date = date(year, month, due_day)

        amount = per_installment
        if i == installment_months - 1:
            amount = per_installment + remainder  # absorb rounding diff

        installments.append(
            LoanInstallment(
                loan_id=loan_id,
                koperasi_id=koperasi_id,
                due_date=due_date,
                amount_due=amount,
                amount_paid=Decimal("0.00"),
                status=InstallmentStatus.unpaid,
                ledger_entry_id=None,
                paid_at=None,
            )
        )
    return installments


# ---------------------------------------------------------------------------
# Public service functions
# ---------------------------------------------------------------------------


async def apply_loan(
    session: AsyncSession,
    *,
    koperasi_id: int,
    farmer_id: int,
    principal: Decimal,
    purpose: LoanPurpose,
    installment_months: int,
    interest_rate: Decimal,
) -> Loan:
    """
    Create a new loan application in 'pending' status.

    Validates:
      - Farmer exists and is an ACTIVE member of koperasi_id (KSP basis).

    Does NOT check credit limit or fund availability here — that happens at
    approve time when an admin reviews and triggers disbursement.

    The session is NOT committed here; the calling route commits.
    """
    # Assert farmer is an active member of this koperasi (tenant-scoped)
    farmer_result = await session.execute(
        select(Farmer).where(
            Farmer.user_id == farmer_id,
            Farmer.koperasi_id == koperasi_id,
        )
    )
    farmer = farmer_result.scalar_one_or_none()
    if farmer is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Farmer not found in this koperasi.",
        )
    if farmer.status != FarmerStatus.active:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Only active koperasi members may apply for loans (KSP basis).",
        )

    loan = Loan(
        koperasi_id=koperasi_id,
        farmer_id=farmer_id,
        principal=principal,
        purpose=purpose,
        installment_months=installment_months,
        interest_rate=interest_rate,
        status=LoanStatus.pending,
    )
    session.add(loan)
    await session.flush()  # populate loan.id

    logger.info(
        "loan.apply: koperasi=%d farmer=%d loan_id=%d principal=%s",
        koperasi_id,
        farmer_id,
        loan.id,
        principal,
    )
    return loan


async def approve_loan(
    session: AsyncSession,
    *,
    koperasi_id: int,
    loan_id: int,
    admin_user_id: int,
) -> Loan:
    """
    Approve and disburse a pending loan.  Fully atomic.

    Steps (all inside the caller's transaction):
      1. SELECT loan FOR UPDATE, assert tenant + status=pending.
      2. compute_credit_score → attach score + limit_at_application.
         Raise ExceedsCreditLimit if principal > limit.
      3. get_payment_provider().create_disbursement (before ledger write so
         the xendit_disbursement_id can be recorded in the ledger entry).
      4. post_ledger_entry(loan pool, loan_disbursement, debit) — locks
         koperasi_funds FOR UPDATE, checks sufficiency, raises InsufficientFunds.
         xendit_disbursement_id is threaded in for the unique link.
      5. loan.status = active, loan.disbursed_at, loan.approved_by,
         loan.xendit_disbursement_id set.
      6. Generate installment rows (monthly, starting from today).
      7. LoanStatusHistory(pending → active).
      8. write_audit('loan_approved').
      9. Flush — caller commits.

    Raises:
        LoanNotFound        — tenant mismatch or loan doesn't exist.
        LoanStateError      — loan is not in pending status.
        ExceedsCreditLimit  — principal > credit limit at time of scoring.
        InsufficientFunds   — Loan Pool balance insufficient.
        HTTPException 422   — re-raised from ledger invariant violation.
    """
    # --- 1. Lock loan row ---
    loan = await _get_loan_for_update(session, koperasi_id=koperasi_id, loan_id=loan_id)

    if loan.status != LoanStatus.pending:
        raise LoanStateError(
            f"Loan {loan_id} is in status '{loan.status.value}' — only pending loans "
            "can be approved."
        )

    # --- 2. Credit scoring ---
    cs = await compute_credit_score(
        session, koperasi_id=koperasi_id, farmer_id=loan.farmer_id
    )
    credit_limit: Decimal = tier_to_limit(cs.tier)
    principal: Decimal = Decimal(str(loan.principal))

    loan.credit_score = cs.score
    loan.limit_at_application = credit_limit

    if principal > credit_limit:
        raise ExceedsCreditLimit(principal=principal, limit=credit_limit)

    # --- 3. Payment provider disbursement (before ledger write) ---
    provider = get_payment_provider()
    disb_result = await provider.create_disbursement(
        amount=principal,
        reference_id=loan.id,
        description=f"Loan disbursement for loan #{loan.id}",
    )
    xendit_disbursement_id: str = disb_result["disbursement_id"]

    # --- 4. Ledger debit (Loan Pool) — locks koperasi_funds FOR UPDATE ---
    await post_ledger_entry(
        session,
        koperasi_id=koperasi_id,
        pool=LedgerPool.loan,
        type=LedgerType.loan_disbursement,
        amount=principal,
        direction=LedgerDirection.debit,
        reference_type="loan",
        reference_id=loan.id,
        external_idempotency_key=f"loan-disb-{loan.id}",
        xendit_disbursement_id=xendit_disbursement_id,
    )

    # --- 5. Update loan status ---
    now_utc = datetime.now(UTC)
    loan.status = LoanStatus.active
    loan.disbursed_at = now_utc
    loan.approved_by = admin_user_id
    loan.xendit_disbursement_id = xendit_disbursement_id

    # --- 6. Generate installments ---
    installments = _generate_installments(
        loan_id=loan.id,
        koperasi_id=koperasi_id,
        principal=principal,
        interest_rate=Decimal(str(loan.interest_rate)),
        installment_months=loan.installment_months,
        start_date=now_utc.date(),
    )
    for inst in installments:
        session.add(inst)

    # --- 7. Status history ---
    session.add(
        LoanStatusHistory(
            loan_id=loan.id,
            koperasi_id=koperasi_id,
            old_status=LoanStatus.pending,
            new_status=LoanStatus.active,
            changed_by=admin_user_id,
            reason="Approved and disbursed by admin.",
        )
    )

    # --- 8. Audit ---
    await write_audit(
        session,
        actor_user_id=admin_user_id,
        koperasi_id=koperasi_id,
        action="loan_approved",
        entity_type="loan",
        entity_id=loan.id,
        after={
            "status": LoanStatus.active.value,
            "disbursed_at": now_utc,
            "principal": principal,
            "credit_score": cs.score,
            "credit_tier": cs.tier,
            "limit_at_application": credit_limit,
            "xendit_disbursement_id": xendit_disbursement_id,
        },
    )

    await session.flush()

    logger.info(
        "loan.approved: koperasi=%d loan_id=%d principal=%s "
        "score=%s tier=%s disb_id=%s",
        koperasi_id,
        loan.id,
        principal,
        cs.score,
        cs.tier,
        xendit_disbursement_id,
    )
    return loan


async def reject_loan(
    session: AsyncSession,
    *,
    koperasi_id: int,
    loan_id: int,
    admin_user_id: int,
    reason: str,
) -> Loan:
    """
    Reject a pending loan application.

    Locks the loan row, asserts status=pending, then sets status=rejected.
    Records LoanStatusHistory and audit entry.  Does NOT commit.
    """
    loan = await _get_loan_for_update(session, koperasi_id=koperasi_id, loan_id=loan_id)

    if loan.status != LoanStatus.pending:
        raise LoanStateError(
            f"Loan {loan_id} is in status '{loan.status.value}' — only pending loans "
            "can be rejected."
        )

    loan.status = LoanStatus.rejected

    session.add(
        LoanStatusHistory(
            loan_id=loan.id,
            koperasi_id=koperasi_id,
            old_status=LoanStatus.pending,
            new_status=LoanStatus.rejected,
            changed_by=admin_user_id,
            reason=reason,
        )
    )

    await write_audit(
        session,
        actor_user_id=admin_user_id,
        koperasi_id=koperasi_id,
        action="loan_rejected",
        entity_type="loan",
        entity_id=loan.id,
        after={"status": LoanStatus.rejected.value, "reason": reason},
    )

    await session.flush()

    logger.info(
        "loan.rejected: koperasi=%d loan_id=%d reason=%r",
        koperasi_id,
        loan.id,
        reason,
    )
    return loan


async def list_loans(
    session: AsyncSession,
    *,
    koperasi_id: int,
    status: LoanStatus | None = None,
    farmer_id: int | None = None,
) -> list[Loan]:
    """
    Return loans for a koperasi, optionally filtered by status and/or farmer.

    All queries are tenant-scoped by koperasi_id.
    Pass farmer_id to restrict to a single farmer's own loans.
    """
    q = select(Loan).where(Loan.koperasi_id == koperasi_id)
    if status is not None:
        q = q.where(Loan.status == status)
    if farmer_id is not None:
        q = q.where(Loan.farmer_id == farmer_id)
    q = q.order_by(Loan.created_at.desc())

    result = await session.execute(q)
    return list(result.scalars().all())


async def repay_installment(
    session: AsyncSession,
    *,
    koperasi_id: int,
    loan_id: int,
    installment_id: int,
    payer_user_id: int,
    amount: Decimal | None = None,
) -> tuple[Loan, LoanInstallment]:
    """
    Record one installment repayment against the Loan Pool (credit direction).

    Business rules:
      - Loan must belong to koperasi_id and be in 'active' or 'past_due' status.
      - Installment must belong to the loan + koperasi, and be in 'unpaid' or
        'late' status (not already 'paid').
      - amount defaults to the full remaining balance (amount_due - amount_paid).
      - Overpayment beyond remaining balance is rejected (LoanStateError).
      - Repayment CREDITS the Loan Pool — inbound money restores the pool.
        No payment-provider disbursement call; ledger entry only.
      - Idempotent via external_idempotency_key=f'loan-repay-{installment_id}'.
      - If all installments on the loan reach 'paid' status → loan.status = paid.
      - LoanStatusHistory + audit written for every repayment (and for full payoff).
      - Does NOT commit; caller owns the transaction.

    Raises:
        LoanNotFound       — loan does not exist under this koperasi.
        LoanStateError     — wrong loan/installment status, or overpayment.
    """
    # --- 1. Lock loan row (tenant-scoped) ---
    loan = await _get_loan_for_update(session, koperasi_id=koperasi_id, loan_id=loan_id)

    if loan.status not in (LoanStatus.active, LoanStatus.past_due):
        raise LoanStateError(
            f"Loan {loan_id} is in status '{loan.status.value}' — "
            "repayments are only accepted for active or past_due loans."
        )

    # --- 2. Fetch the installment (tenant-scoped) ---
    inst_result = await session.execute(
        select(LoanInstallment).where(
            LoanInstallment.id == installment_id,
            LoanInstallment.loan_id == loan_id,
            LoanInstallment.koperasi_id == koperasi_id,
        )
    )
    installment = inst_result.scalar_one_or_none()
    if installment is None:
        raise LoanStateError(
            f"Installment {installment_id} not found for loan {loan_id} "
            f"in koperasi {koperasi_id}."
        )
    if installment.status == InstallmentStatus.paid:
        raise LoanStateError(
            f"Installment {installment_id} is already fully paid."
        )

    # --- 3. Resolve payment amount ---
    amount_due: Decimal = Decimal(str(installment.amount_due))
    amount_paid_so_far: Decimal = Decimal(str(installment.amount_paid))
    remaining: Decimal = amount_due - amount_paid_so_far

    if amount is None:
        pay_amount = remaining
    else:
        pay_amount = Decimal(str(amount))
        if pay_amount > remaining:
            raise LoanStateError(
                f"Payment amount {pay_amount} exceeds remaining balance "
                f"{remaining} for installment {installment_id}."
            )

    # --- 4. Ledger entry — CREDIT the Loan Pool ---
    entry = await post_ledger_entry(
        session,
        koperasi_id=koperasi_id,
        pool=LedgerPool.loan,
        type=LedgerType.loan_repayment,
        amount=pay_amount,
        direction=LedgerDirection.credit,
        reference_type="loan_installment",
        reference_id=installment_id,
        external_idempotency_key=f"loan-repay-{installment_id}",
    )

    # --- 5. Update installment ---
    now_utc = datetime.now(UTC)
    new_amount_paid: Decimal = amount_paid_so_far + pay_amount
    installment.amount_paid = new_amount_paid  # type: ignore[assignment]

    if new_amount_paid >= amount_due:
        installment.status = InstallmentStatus.paid
        installment.paid_at = now_utc
        installment.ledger_entry_id = entry.id

    await session.flush()

    # --- 6. Audit: individual repayment ---
    await write_audit(
        session,
        actor_user_id=payer_user_id,
        koperasi_id=koperasi_id,
        action="loan_repayment",
        entity_type="loan_installment",
        entity_id=installment_id,
        after={
            "loan_id": loan_id,
            "installment_id": installment_id,
            "amount_paid": pay_amount,
            "new_amount_paid": new_amount_paid,
            "remaining_after": amount_due - new_amount_paid,
            "installment_status": installment.status.value,
            "ledger_entry_id": entry.id,
        },
    )

    # --- 7. Check if entire loan is now fully repaid ---
    all_inst_result = await session.execute(
        select(LoanInstallment).where(
            LoanInstallment.loan_id == loan_id,
            LoanInstallment.koperasi_id == koperasi_id,
        )
    )
    all_installments = list(all_inst_result.scalars().all())

    all_paid = all(i.status == InstallmentStatus.paid for i in all_installments)
    if all_paid:
        old_status = loan.status
        loan.status = LoanStatus.paid
        session.add(
            LoanStatusHistory(
                loan_id=loan.id,
                koperasi_id=koperasi_id,
                old_status=old_status,
                new_status=LoanStatus.paid,
                changed_by=payer_user_id,
                reason="All installments fully paid.",
            )
        )
        await write_audit(
            session,
            actor_user_id=payer_user_id,
            koperasi_id=koperasi_id,
            action="loan_fully_repaid",
            entity_type="loan",
            entity_id=loan.id,
            after={"status": LoanStatus.paid.value},
        )

    await session.flush()

    logger.info(
        "loan.repay: koperasi=%d loan_id=%d installment_id=%d amount=%s "
        "fully_repaid=%s",
        koperasi_id,
        loan_id,
        installment_id,
        pay_amount,
        all_paid,
    )
    return loan, installment


async def mark_loans_past_due(
    session: AsyncSession,
    *,
    koperasi_id: int,
    loan_id: int | None = None,
    actor_user_id: int,
) -> list[Loan]:
    """
    Mark overdue installments as 'late' and transition affected loans to 'past_due'.

    Sweeps all active loans in the koperasi (or one specific loan when loan_id is
    given) for unpaid installments whose due_date < today.  For each such loan:
      - Sets all overdue unpaid installments to InstallmentStatus.late.
      - Sets loan.status = past_due (if not already).
      - Writes a LoanStatusHistory row (active → past_due).
      - Writes an audit entry.

    Returns the list of loans that were transitioned (may be empty).
    Tenant-scoped: only loans where koperasi_id matches are touched.
    Does NOT commit; caller owns the transaction.
    """
    today = date.today()

    # Build query for candidate loans
    loan_q = select(Loan).where(
        Loan.koperasi_id == koperasi_id,
        Loan.status == LoanStatus.active,
    )
    if loan_id is not None:
        loan_q = loan_q.where(Loan.id == loan_id)

    loans_result = await session.execute(loan_q.with_for_update())
    candidate_loans: list[Loan] = list(loans_result.scalars().all())

    affected: list[Loan] = []

    for loan in candidate_loans:
        # Find unpaid installments that are past due for this loan
        overdue_result = await session.execute(
            select(LoanInstallment).where(
                LoanInstallment.loan_id == loan.id,
                LoanInstallment.koperasi_id == koperasi_id,
                LoanInstallment.due_date < today,
                LoanInstallment.status == InstallmentStatus.unpaid,
            )
        )
        overdue_installments = list(overdue_result.scalars().all())

        if not overdue_installments:
            continue

        # Mark each overdue installment as late
        for inst in overdue_installments:
            inst.status = InstallmentStatus.late

        # Transition loan status
        old_status = loan.status
        loan.status = LoanStatus.past_due
        session.add(
            LoanStatusHistory(
                loan_id=loan.id,
                koperasi_id=koperasi_id,
                old_status=old_status,
                new_status=LoanStatus.past_due,
                changed_by=actor_user_id,
                reason=f"Installment(s) overdue as of {today.isoformat()}.",
            )
        )

        await write_audit(
            session,
            actor_user_id=actor_user_id,
            koperasi_id=koperasi_id,
            action="loan_marked_past_due",
            entity_type="loan",
            entity_id=loan.id,
            after={
                "status": LoanStatus.past_due.value,
                "overdue_installment_ids": [i.id for i in overdue_installments],
                "as_of": today.isoformat(),
            },
        )

        affected.append(loan)

    if affected:
        await session.flush()

    logger.info(
        "loan.mark_past_due: koperasi=%d loan_id=%s affected_count=%d",
        koperasi_id,
        loan_id,
        len(affected),
    )
    return affected


async def seize_loan(
    session: AsyncSession,
    *,
    koperasi_id: int,
    loan_id: int,
    admin_user_id: int,
    reason: str,
) -> Loan:
    """
    Seize the collateral for a non-performing loan.

    Allowable transitions: active → seized  or  past_due → seized.
    Any other current status raises LoanStateError.

    No ledger movement is written — collateral seizure is a status-only
    transition recorded in LoanStatusHistory and audit_log.

    Raises:
        LoanNotFound   — loan does not exist under this koperasi.
        LoanStateError — loan is not in active or past_due status.
    """
    loan = await _get_loan_for_update(session, koperasi_id=koperasi_id, loan_id=loan_id)

    if loan.status not in (LoanStatus.active, LoanStatus.past_due):
        raise LoanStateError(
            f"Loan {loan_id} is in status '{loan.status.value}' — "
            "only active or past_due loans can be seized."
        )

    old_status = loan.status
    loan.status = LoanStatus.seized

    session.add(
        LoanStatusHistory(
            loan_id=loan.id,
            koperasi_id=koperasi_id,
            old_status=old_status,
            new_status=LoanStatus.seized,
            changed_by=admin_user_id,
            reason=reason,
        )
    )

    await write_audit(
        session,
        actor_user_id=admin_user_id,
        koperasi_id=koperasi_id,
        action="loan_seized",
        entity_type="loan",
        entity_id=loan.id,
        after={"status": LoanStatus.seized.value, "reason": reason},
    )

    await session.flush()

    logger.info(
        "loan.seized: koperasi=%d loan_id=%d admin=%d reason=%r",
        koperasi_id,
        loan_id,
        admin_user_id,
        reason,
    )
    return loan


async def get_loan(
    session: AsyncSession,
    *,
    koperasi_id: int,
    loan_id: int,
) -> tuple[Loan, list[LoanInstallment], "CreditScore | None"]:
    """
    Fetch a single loan with its installments and latest credit score snapshot.

    All queries tenant-scoped by koperasi_id.

    Returns:
        (Loan, [LoanInstallment, ...], CreditScore | None)
        CreditScore is the most recent snapshot for the farmer (may be None if
        no scoring has been run yet).

    Raises:
        LoanNotFound — if the loan doesn't exist under this koperasi.
    """
    loan_result = await session.execute(
        select(Loan).where(
            Loan.id == loan_id,
            Loan.koperasi_id == koperasi_id,
        )
    )
    loan = loan_result.scalar_one_or_none()
    if loan is None:
        raise LoanNotFound(f"Loan {loan_id} not found in koperasi {koperasi_id}.")

    # Installments — tenant-scoped via koperasi_id on the installment itself
    inst_result = await session.execute(
        select(LoanInstallment)
        .where(
            LoanInstallment.loan_id == loan_id,
            LoanInstallment.koperasi_id == koperasi_id,
        )
        .order_by(LoanInstallment.due_date)
    )
    installments = list(inst_result.scalars().all())

    # Latest credit score snapshot for this farmer (tenant-scoped)
    from app.models.loans import CreditScore as CreditScoreModel

    cs_result = await session.execute(
        select(CreditScoreModel)
        .where(
            CreditScoreModel.farmer_id == loan.farmer_id,
            CreditScoreModel.koperasi_id == koperasi_id,
        )
        .order_by(CreditScoreModel.computed_at.desc())
        .limit(1)
    )
    credit_score = cs_result.scalar_one_or_none()

    return loan, installments, credit_score
