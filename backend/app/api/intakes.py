from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import CurrentUser, get_tenant_id, require_role
from app.db.engine import get_session
from app.models.enums import IntakeStatus, UserRole
from app.schemas.intakes import (
    HarvestIntakeOut,
    IntakeConfirmRequest,
    IntakeCreateRequest,
    IntakeRejectRequest,
    QRVerifyOut,
    QRVerifyRequest,
)
from app.services.intakes import (
    IntakeNotFound,
    IntakeStateError,
    confirm_intake,
    create_intake,
    get_intake,
    list_intakes,
    reject_intake,
    verify_harvest_qr_for_tenant,
)
from app.services.ledger import InsufficientFunds
from app.services.qr import QRVerificationError

router = APIRouter(prefix="/intakes", tags=["intakes"])


@router.post("", response_model=HarvestIntakeOut, status_code=status.HTTP_201_CREATED)
async def create_my_intake(
    body: IntakeCreateRequest,
    current_user: CurrentUser = Depends(require_role(UserRole.farmer)),
    session: AsyncSession = Depends(get_session),
) -> HarvestIntakeOut:
    koperasi_id = get_tenant_id(current_user)
    async with session.begin():
        intake = await create_intake(
            session,
            koperasi_id=koperasi_id,
            farmer_id=current_user.user_id,
            commodity_id=body.commodity_id,
            weight_kg=body.weight_kg,
        )
    return HarvestIntakeOut.model_validate(intake)


@router.get("/mine", response_model=list[HarvestIntakeOut])
async def list_my_intakes(
    status_filter: IntakeStatus | None = Query(default=None, alias="status"),
    current_user: CurrentUser = Depends(require_role(UserRole.farmer)),
    session: AsyncSession = Depends(get_session),
) -> list[HarvestIntakeOut]:
    koperasi_id = get_tenant_id(current_user)
    rows = await list_intakes(
        session,
        koperasi_id=koperasi_id,
        farmer_id=current_user.user_id,
        status_filter=status_filter,
    )
    return [HarvestIntakeOut.model_validate(row) for row in rows]


@router.get("", response_model=list[HarvestIntakeOut])
async def list_tenant_intakes(
    status_filter: IntakeStatus | None = Query(default=None, alias="status"),
    current_user: CurrentUser = Depends(require_role(UserRole.manager, UserRole.admin)),
    session: AsyncSession = Depends(get_session),
) -> list[HarvestIntakeOut]:
    koperasi_id = get_tenant_id(current_user)
    rows = await list_intakes(session, koperasi_id=koperasi_id, status_filter=status_filter)
    return [HarvestIntakeOut.model_validate(row) for row in rows]


@router.get("/{intake_id}", response_model=HarvestIntakeOut)
async def get_one_intake(
    intake_id: int,
    current_user: CurrentUser = Depends(require_role(UserRole.farmer, UserRole.manager, UserRole.admin)),
    session: AsyncSession = Depends(get_session),
) -> HarvestIntakeOut:
    koperasi_id = get_tenant_id(current_user)
    farmer_id = current_user.user_id if current_user.role == UserRole.farmer else None
    try:
        intake = await get_intake(
            session,
            koperasi_id=koperasi_id,
            intake_id=intake_id,
            farmer_id=farmer_id,
        )
    except IntakeNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return HarvestIntakeOut.model_validate(intake)


@router.post("/{intake_id}/confirm", response_model=HarvestIntakeOut)
async def confirm_one_intake(
    intake_id: int,
    body: IntakeConfirmRequest,
    current_user: CurrentUser = Depends(require_role(UserRole.manager, UserRole.admin)),
    session: AsyncSession = Depends(get_session),
) -> HarvestIntakeOut:
    koperasi_id = get_tenant_id(current_user)
    async with session.begin():
        try:
            intake = await confirm_intake(
                session,
                koperasi_id=koperasi_id,
                intake_id=intake_id,
                manager_user_id=current_user.user_id,
                weight_kg=body.weight_kg,
            )
        except IntakeNotFound as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
        except IntakeStateError as exc:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
        except InsufficientFunds as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Insufficient Marginal Profit Pool: available={exc.available}, requested={exc.requested}.",
            ) from exc
    return HarvestIntakeOut.model_validate(intake)


@router.post("/{intake_id}/reject", response_model=HarvestIntakeOut)
async def reject_one_intake(
    intake_id: int,
    body: IntakeRejectRequest,
    current_user: CurrentUser = Depends(require_role(UserRole.manager, UserRole.admin)),
    session: AsyncSession = Depends(get_session),
) -> HarvestIntakeOut:
    koperasi_id = get_tenant_id(current_user)
    async with session.begin():
        try:
            intake = await reject_intake(
                session,
                koperasi_id=koperasi_id,
                intake_id=intake_id,
                manager_user_id=current_user.user_id,
                reason=body.reason,
            )
        except IntakeNotFound as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
        except IntakeStateError as exc:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return HarvestIntakeOut.model_validate(intake)


@router.post("/verify-qr", response_model=QRVerifyOut)
async def verify_intake_qr(
    body: QRVerifyRequest,
    current_user: CurrentUser = Depends(require_role(UserRole.manager, UserRole.admin)),
    session: AsyncSession = Depends(get_session),
) -> QRVerifyOut:
    koperasi_id = get_tenant_id(current_user)
    try:
        payload = await verify_harvest_qr_for_tenant(
            session,
            koperasi_id=koperasi_id,
            token=body.token,
        )
    except (QRVerificationError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    except IntakeNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return QRVerifyOut(valid=True, payload=payload)
