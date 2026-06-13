from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import CurrentUser, get_tenant_id, require_role
from app.db.engine import get_session
from app.models.enums import OrderStatus, UserRole
from app.schemas.orders import (
    CatalogItemOut,
    FulfillmentOut,
    MockInvoiceWebhookRequest,
    OrderCreate,
    OrderDetailOut,
    OrderItemOut,
    OrderOut,
    PickupVerifyRequest,
    WebhookProcessOut,
)
from app.services.fulfillment import (
    StockOutError,
    fulfill_paid_order,
    verify_pickup_and_fulfill,
)
from app.services.orders import (
    CommodityUnavailable,
    OrderNotFound,
    OrderStateError,
    WebhookIgnored,
    create_order,
    get_order_detail,
    list_catalog,
    list_orders_for_distributor,
    list_orders_for_koperasi,
    process_invoice_settlement,
)
from app.services.qr import InvalidQrToken

router = APIRouter(tags=["orders"])


def _detail(order, items, payment_url: str | None = None) -> OrderDetailOut:
    return OrderDetailOut(
        **OrderOut.model_validate(order).model_dump(),
        items=[OrderItemOut.model_validate(item) for item in items],
        payment_url=payment_url,
    )


@router.get("/marketplace/catalog", response_model=list[CatalogItemOut])
async def browse_catalog(
    koperasi_id: int | None = None,
    in_stock_only: bool = True,
    current_user: CurrentUser = Depends(require_role(UserRole.distributor)),
    session: AsyncSession = Depends(get_session),
) -> list[CatalogItemOut]:
    del current_user
    commodities = await list_catalog(
        session,
        koperasi_id=koperasi_id,
        in_stock_only=in_stock_only,
    )
    return [CatalogItemOut.model_validate(commodity) for commodity in commodities]


@router.post(
    "/marketplace/orders",
    response_model=OrderDetailOut,
    status_code=status.HTTP_201_CREATED,
)
async def checkout_order(
    body: OrderCreate,
    current_user: CurrentUser = Depends(require_role(UserRole.distributor)),
    session: AsyncSession = Depends(get_session),
) -> OrderDetailOut:
    try:
        async with session.begin():
            checkout = await create_order(
                session,
                distributor_id=current_user.user_id,
                koperasi_id=body.koperasi_id,
                fulfillment_type=body.fulfillment_type,
                delivery_address=body.delivery_address,
                items=[(item.commodity_id, item.weight_kg) for item in body.items],
            )
    except CommodityUnavailable as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

    return _detail(checkout.order, checkout.items, checkout.payment_url)


@router.get("/marketplace/orders", response_model=list[OrderOut])
async def list_my_orders(
    current_user: CurrentUser = Depends(require_role(UserRole.distributor)),
    session: AsyncSession = Depends(get_session),
) -> list[OrderOut]:
    orders = await list_orders_for_distributor(session, distributor_id=current_user.user_id)
    return [OrderOut.model_validate(order) for order in orders]


@router.get("/marketplace/orders/{order_id}", response_model=OrderDetailOut)
async def get_my_order(
    order_id: int,
    current_user: CurrentUser = Depends(require_role(UserRole.distributor)),
    session: AsyncSession = Depends(get_session),
) -> OrderDetailOut:
    try:
        order, items = await get_order_detail(
            session,
            order_id=order_id,
            distributor_id=current_user.user_id,
        )
    except OrderNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return _detail(order, items)


@router.get("/orders", response_model=list[OrderOut])
async def list_koperasi_orders(
    status_filter: OrderStatus | None = None,
    current_user: CurrentUser = Depends(require_role(UserRole.manager, UserRole.admin)),
    session: AsyncSession = Depends(get_session),
) -> list[OrderOut]:
    koperasi_id = get_tenant_id(current_user)
    orders = await list_orders_for_koperasi(session, koperasi_id=koperasi_id, status=status_filter)
    return [OrderOut.model_validate(order) for order in orders]


@router.get("/orders/{order_id}", response_model=OrderDetailOut)
async def get_koperasi_order(
    order_id: int,
    current_user: CurrentUser = Depends(require_role(UserRole.manager, UserRole.admin)),
    session: AsyncSession = Depends(get_session),
) -> OrderDetailOut:
    koperasi_id = get_tenant_id(current_user)
    try:
        order, items = await get_order_detail(session, order_id=order_id, koperasi_id=koperasi_id)
    except OrderNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return _detail(order, items)


@router.post("/orders/pickup/verify", response_model=FulfillmentOut)
async def verify_pickup(
    body: PickupVerifyRequest,
    current_user: CurrentUser = Depends(require_role(UserRole.manager, UserRole.admin)),
    session: AsyncSession = Depends(get_session),
) -> FulfillmentOut:
    koperasi_id = get_tenant_id(current_user)
    try:
        async with session.begin():
            result = await verify_pickup_and_fulfill(
                session,
                koperasi_id=koperasi_id,
                token=body.token,
                actor_user_id=current_user.user_id,
            )
    except InvalidQrToken as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    except OrderNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except OrderStateError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except StockOutError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail={"message": str(exc), "shortages": exc.shortages}) from exc

    return FulfillmentOut(
        order=_detail(result.order, result.items),
        released_stock_movements=len(result.stock_movements),
    )


@router.post("/orders/{order_id}/fulfill-delivery", response_model=FulfillmentOut)
async def fulfill_delivery_order(
    order_id: int,
    current_user: CurrentUser = Depends(require_role(UserRole.manager, UserRole.admin)),
    session: AsyncSession = Depends(get_session),
) -> FulfillmentOut:
    koperasi_id = get_tenant_id(current_user)
    try:
        async with session.begin():
            result = await fulfill_paid_order(
                session,
                koperasi_id=koperasi_id,
                order_id=order_id,
                actor_user_id=current_user.user_id,
            )
    except OrderNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except OrderStateError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except StockOutError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail={"message": str(exc), "shortages": exc.shortages}) from exc

    return FulfillmentOut(
        order=_detail(result.order, result.items),
        released_stock_movements=len(result.stock_movements),
    )


@router.post("/webhooks/xendit/mock-invoice", response_model=WebhookProcessOut)
async def mock_invoice_webhook(
    body: MockInvoiceWebhookRequest,
    current_user: CurrentUser = Depends(require_role(UserRole.platform_admin)),
    session: AsyncSession = Depends(get_session),
) -> WebhookProcessOut:
    del current_user
    try:
        async with session.begin():
            result = await process_invoice_settlement(
                session,
                event_id=body.event_id,
                invoice_id=body.invoice_id,
                payload=body.model_dump(mode="json"),
            )
    except WebhookIgnored as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    return WebhookProcessOut(
        event_id=result.event_id,
        status=result.status,
        order_id=result.order_id,
        detail=result.detail,
    )
