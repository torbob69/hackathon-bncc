from __future__ import annotations

import logging
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal
from uuid import uuid4

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.commodities import Commodity
from app.models.enums import (
    FarmerStatus,
    IntakeStatus,
    LedgerDirection,
    LedgerPool,
    LedgerType,
    NotificationType,
    StockDirection,
)
from app.models.intakes import HarvestIntake, StockMovement
from app.models.koperasi import KoperasiFunds
from app.models.users import Farmer
from app.payments import get_payment_provider
from app.services.audit import write_audit
from app.services.ledger import InsufficientFunds, post_ledger_entry
from app.services.notifications import create_notification, notify_tenant_managers
from app.services.qr import sign_harvest_intake_qr, verify_qr_token

logger = logging.getLogger(__name__)

MONEY = Decimal("0.01")
WEIGHT = Decimal("0.001")


class IntakeNotFound(Exception):
    pass


class IntakeStateError(Exception):
    pass


def _money(value: Decimal) -> Decimal:
    return Decimal(str(value)).quantize(MONEY, rounding=ROUND_HALF_UP)


def _weight(value: Decimal) -> Decimal:
    return Decimal(str(value)).quantize(WEIGHT, rounding=ROUND_HALF_UP)


async def _get_available_margin_pool(
    session: AsyncSession,
    *,
    koperasi_id: int,
    lock: bool = False,
) -> Decimal:
    stmt = select(KoperasiFunds).where(KoperasiFunds.koperasi_id == koperasi_id)
    if lock:
        stmt = stmt.with_for_update()
    result = await session.execute(stmt)
    funds = result.scalar_one_or_none()
    if funds is None:
        return Decimal("0.00")
    return Decimal(str(funds.marginal_profit_pool_balance))


async def _get_intake_for_update(
    session: AsyncSession,
    *,
    koperasi_id: int,
    intake_id: int,
) -> HarvestIntake:
    result = await session.execute(
        select(HarvestIntake)
        .where(HarvestIntake.id == intake_id, HarvestIntake.koperasi_id == koperasi_id)
        .with_for_update()
    )
    intake = result.scalar_one_or_none()
    if intake is None:
        raise IntakeNotFound(f"Intake {intake_id} not found in this koperasi.")
    return intake


async def create_intake(
    session: AsyncSession,
    *,
    koperasi_id: int,
    farmer_id: int,
    commodity_id: int,
    weight_kg: Decimal,
) -> HarvestIntake:
    farmer_result = await session.execute(
        select(Farmer).where(Farmer.user_id == farmer_id, Farmer.koperasi_id == koperasi_id)
    )
    farmer = farmer_result.scalar_one_or_none()
    if farmer is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Farmer not found.")
    if farmer.status != FarmerStatus.active:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Only active farmers can create harvest intakes.",
        )

    commodity_result = await session.execute(
        select(Commodity).where(
            Commodity.id == commodity_id,
            Commodity.koperasi_id == koperasi_id,
        )
    )
    commodity = commodity_result.scalar_one_or_none()
    if commodity is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Commodity not found.")

    weight = _weight(weight_kg)
    estimated_value = _money(weight * Decimal(str(commodity.pihps_price)))
    available = await _get_available_margin_pool(session, koperasi_id=koperasi_id)
    exceeds_pool = estimated_value > available

    intake = HarvestIntake(
        koperasi_id=koperasi_id,
        farmer_id=farmer_id,
        commodity_id=commodity_id,
        weight_kg=weight,
        qr_token=f"pending-{uuid4().hex}",
        status=IntakeStatus.pending,
        estimated_value=estimated_value,
        exceeds_pool_flag=exceeds_pool,
    )
    session.add(intake)
    await session.flush()

    intake.qr_token = sign_harvest_intake_qr(
        intake_id=intake.id,
        koperasi_id=koperasi_id,
        farmer_id=farmer_id,
        commodity_id=commodity_id,
        weight_kg=weight,
    )

    if exceeds_pool:
        message = (
            f"Estimated intake value Rp {estimated_value} exceeds available "
            f"Marginal Profit Pool Rp {available}."
        )
        await create_notification(
            session,
            koperasi_id=koperasi_id,
            user_id=farmer_id,
            type=NotificationType.intake_flagged,
            message=message,
            reference_type="harvest_intake",
            reference_id=intake.id,
        )
        await notify_tenant_managers(
            session,
            koperasi_id=koperasi_id,
            type=NotificationType.intake_flagged,
            message=message,
            reference_type="harvest_intake",
            reference_id=intake.id,
        )

    await write_audit(
        session,
        actor_user_id=farmer_id,
        koperasi_id=koperasi_id,
        action="intake_created",
        entity_type="harvest_intake",
        entity_id=intake.id,
        after={
            "commodity_id": commodity_id,
            "weight_kg": weight,
            "estimated_value": estimated_value,
            "exceeds_pool_flag": exceeds_pool,
        },
    )
    await session.flush()
    return intake


async def list_intakes(
    session: AsyncSession,
    *,
    koperasi_id: int,
    farmer_id: int | None = None,
    status_filter: IntakeStatus | None = None,
) -> list[HarvestIntake]:
    stmt = select(HarvestIntake).where(HarvestIntake.koperasi_id == koperasi_id)
    if farmer_id is not None:
        stmt = stmt.where(HarvestIntake.farmer_id == farmer_id)
    if status_filter is not None:
        stmt = stmt.where(HarvestIntake.status == status_filter)
    stmt = stmt.order_by(HarvestIntake.created_at.desc())
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_intake(
    session: AsyncSession,
    *,
    koperasi_id: int,
    intake_id: int,
    farmer_id: int | None = None,
) -> HarvestIntake:
    stmt = select(HarvestIntake).where(
        HarvestIntake.id == intake_id,
        HarvestIntake.koperasi_id == koperasi_id,
    )
    if farmer_id is not None:
        stmt = stmt.where(HarvestIntake.farmer_id == farmer_id)
    result = await session.execute(stmt)
    intake = result.scalar_one_or_none()
    if intake is None:
        raise IntakeNotFound(f"Intake {intake_id} not found in this koperasi.")
    return intake


async def confirm_intake(
    session: AsyncSession,
    *,
    koperasi_id: int,
    intake_id: int,
    manager_user_id: int,
    weight_kg: Decimal | None = None,
) -> HarvestIntake:
    intake = await _get_intake_for_update(session, koperasi_id=koperasi_id, intake_id=intake_id)
    if intake.status != IntakeStatus.pending:
        raise IntakeStateError(f"Only pending intakes can be confirmed; current={intake.status.value}.")

    commodity_result = await session.execute(
        select(Commodity)
        .where(Commodity.id == intake.commodity_id, Commodity.koperasi_id == koperasi_id)
        .with_for_update()
    )
    commodity = commodity_result.scalar_one_or_none()
    if commodity is None:
        raise IntakeNotFound("Intake commodity not found in this koperasi.")

    final_weight = _weight(weight_kg if weight_kg is not None else Decimal(str(intake.weight_kg)))
    price = _money(Decimal(str(commodity.pihps_price)))
    total = _money(final_weight * price)
    available = await _get_available_margin_pool(session, koperasi_id=koperasi_id, lock=True)
    if total > available:
        intake.exceeds_pool_flag = True
        message = (
            f"Intake #{intake.id} cannot be confirmed yet: requested Rp {total}, "
            f"available pool Rp {available}."
        )
        await create_notification(
            session,
            koperasi_id=koperasi_id,
            user_id=intake.farmer_id,
            type=NotificationType.intake_flagged,
            message=message,
            reference_type="harvest_intake",
            reference_id=intake.id,
        )
        await notify_tenant_managers(
            session,
            koperasi_id=koperasi_id,
            type=NotificationType.intake_flagged,
            message=message,
            reference_type="harvest_intake",
            reference_id=intake.id,
        )
        raise InsufficientFunds(LedgerPool.marginal_profit, available, total)

    provider = get_payment_provider()
    disb_result = await provider.create_disbursement(
        amount=total,
        reference_id=intake.id,
        description=f"Harvest intake payment #{intake.id}",
    )

    await post_ledger_entry(
        session,
        koperasi_id=koperasi_id,
        pool=LedgerPool.marginal_profit,
        type=LedgerType.farmer_payment,
        amount=total,
        direction=LedgerDirection.debit,
        reference_type="harvest_intake",
        reference_id=intake.id,
        external_idempotency_key=f"intake-pay-{intake.id}",
        xendit_disbursement_id=disb_result["disbursement_id"],
    )

    now = datetime.now(UTC)
    before = {"status": intake.status.value, "weight_kg": intake.weight_kg}
    intake.weight_kg = final_weight
    intake.estimated_value = total
    intake.price_per_kg = price
    intake.total_paid = total
    intake.status = IntakeStatus.confirmed
    intake.confirmed_by = manager_user_id
    intake.confirmed_at = now
    intake.exceeds_pool_flag = False

    commodity.current_stock_kg = _weight(Decimal(str(commodity.current_stock_kg)) + final_weight)
    session.add(
        StockMovement(
            koperasi_id=koperasi_id,
            commodity_id=commodity.id,
            direction=StockDirection.in_,
            weight_kg=final_weight,
            reference_type="harvest_intake",
            reference_id=intake.id,
            qr_token=intake.qr_token,
            created_by=manager_user_id,
        )
    )
    await create_notification(
        session,
        koperasi_id=koperasi_id,
        user_id=intake.farmer_id,
        type=NotificationType.intake_confirmed,
        message=f"Harvest intake #{intake.id} confirmed for Rp {total}.",
        reference_type="harvest_intake",
        reference_id=intake.id,
    )
    await write_audit(
        session,
        actor_user_id=manager_user_id,
        koperasi_id=koperasi_id,
        action="intake_confirmed",
        entity_type="harvest_intake",
        entity_id=intake.id,
        before=before,
        after={
            "status": IntakeStatus.confirmed.value,
            "weight_kg": final_weight,
            "price_per_kg": price,
            "total_paid": total,
            "xendit_disbursement_id": disb_result["disbursement_id"],
        },
    )
    await session.flush()
    return intake


async def reject_intake(
    session: AsyncSession,
    *,
    koperasi_id: int,
    intake_id: int,
    manager_user_id: int,
    reason: str,
) -> HarvestIntake:
    intake = await _get_intake_for_update(session, koperasi_id=koperasi_id, intake_id=intake_id)
    if intake.status != IntakeStatus.pending:
        raise IntakeStateError(f"Only pending intakes can be rejected; current={intake.status.value}.")

    before = {"status": intake.status.value}
    intake.status = IntakeStatus.rejected
    intake.reject_reason = reason
    intake.confirmed_by = manager_user_id
    intake.confirmed_at = datetime.now(UTC)
    await create_notification(
        session,
        koperasi_id=koperasi_id,
        user_id=intake.farmer_id,
        type=NotificationType.intake_rejected,
        message=f"Harvest intake #{intake.id} rejected: {reason}",
        reference_type="harvest_intake",
        reference_id=intake.id,
    )
    await write_audit(
        session,
        actor_user_id=manager_user_id,
        koperasi_id=koperasi_id,
        action="intake_rejected",
        entity_type="harvest_intake",
        entity_id=intake.id,
        before=before,
        after={"status": IntakeStatus.rejected.value, "reason": reason},
    )
    await session.flush()
    return intake


async def verify_harvest_qr_for_tenant(
    session: AsyncSession,
    *,
    koperasi_id: int,
    token: str,
) -> dict:
    payload = verify_qr_token(token)
    intake_id = int(payload["sub"])
    intake = await get_intake(session, koperasi_id=koperasi_id, intake_id=intake_id)
    if intake.qr_token != token:
        raise ValueError("QR token does not match the stored intake token.")
    return payload
