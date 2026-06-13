from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.commodities import Commodity
from app.models.enums import FulfillmentType, OrderStatus, StockDirection
from app.models.intakes import StockMovement
from app.models.orders import Order, OrderItem
from app.services.audit import write_audit
from app.services.orders import OrderNotFound, OrderStateError, get_order_detail
from app.services.qr import InvalidQrToken, verify_qr_payload


class StockOutError(Exception):
    def __init__(self, shortages: list[dict]) -> None:
        self.shortages = shortages
        super().__init__("Insufficient stock to fulfill order.")


@dataclass(frozen=True)
class FulfillmentResult:
    order: Order
    items: list[OrderItem]
    stock_movements: list[StockMovement]


async def fulfill_paid_order(
    session: AsyncSession,
    *,
    koperasi_id: int,
    order_id: int,
    actor_user_id: int,
    required_fulfillment_type: FulfillmentType | None = None,
) -> FulfillmentResult:
    order_result = await session.execute(
        select(Order)
        .where(Order.id == order_id, Order.koperasi_id == koperasi_id)
        .with_for_update()
    )
    order = order_result.scalar_one_or_none()
    if order is None:
        raise OrderNotFound(f"Order {order_id} not found in koperasi {koperasi_id}.")
    if order.status != OrderStatus.paid:
        raise OrderStateError(f"Order {order_id} must be paid before fulfillment.")
    if required_fulfillment_type is not None and order.fulfillment_type != required_fulfillment_type:
        raise OrderStateError(f"Order {order_id} is not a {required_fulfillment_type.value} order.")

    item_result = await session.execute(
        select(OrderItem).where(OrderItem.order_id == order.id, OrderItem.koperasi_id == koperasi_id)
    )
    items = list(item_result.scalars().all())

    commodity_ids = [item.commodity_id for item in items]
    commodity_result = await session.execute(
        select(Commodity)
        .where(Commodity.koperasi_id == koperasi_id, Commodity.id.in_(commodity_ids))
        .with_for_update()
    )
    commodities = {commodity.id: commodity for commodity in commodity_result.scalars().all()}

    shortages: list[dict] = []
    for item in items:
        commodity = commodities.get(item.commodity_id)
        available = Decimal(str(commodity.current_stock_kg)) if commodity else Decimal("0")
        requested = Decimal(str(item.weight_kg))
        if available < requested:
            shortages.append(
                {
                    "commodity_id": item.commodity_id,
                    "available_kg": str(available),
                    "requested_kg": str(requested),
                }
            )
    if shortages:
        await write_audit(
            session,
            actor_user_id=actor_user_id,
            koperasi_id=koperasi_id,
            action="order_fulfillment_stock_out",
            entity_type="order",
            entity_id=order.id,
            after={"shortages": shortages},
        )
        raise StockOutError(shortages)

    movements: list[StockMovement] = []
    for item in items:
        commodity = commodities[item.commodity_id]
        commodity.current_stock_kg = Decimal(str(commodity.current_stock_kg)) - Decimal(str(item.weight_kg))
        movement = StockMovement(
            koperasi_id=koperasi_id,
            commodity_id=item.commodity_id,
            direction=StockDirection.out,
            weight_kg=item.weight_kg,
            reference_type="order",
            reference_id=order.id,
            qr_token=order.pickup_qr_token if order.fulfillment_type == FulfillmentType.pickup else None,
            created_by=actor_user_id,
        )
        session.add(movement)
        movements.append(movement)

    order.status = OrderStatus.fulfilled
    await write_audit(
        session,
        actor_user_id=actor_user_id,
        koperasi_id=koperasi_id,
        action="order_fulfilled",
        entity_type="order",
        entity_id=order.id,
        after={
            "status": OrderStatus.fulfilled.value,
            "fulfillment_type": order.fulfillment_type.value,
            "stock_movements": len(movements),
        },
    )
    await session.flush()
    return FulfillmentResult(order=order, items=items, stock_movements=movements)


async def verify_pickup_and_fulfill(
    session: AsyncSession,
    *,
    koperasi_id: int,
    token: str,
    actor_user_id: int,
) -> FulfillmentResult:
    payload = verify_qr_payload(token=token, expected_type="pickup")
    token_koperasi_id = int(payload.get("koperasi_id") or 0)
    order_id = int(payload.get("order_id") or 0)
    if token_koperasi_id != koperasi_id or order_id <= 0:
        raise InvalidQrToken("Pickup QR token does not belong to this koperasi.")

    order, _ = await get_order_detail(session, order_id=order_id, koperasi_id=koperasi_id)
    if order.pickup_qr_token != token:
        raise InvalidQrToken("Pickup QR token does not match the active order token.")

    return await fulfill_paid_order(
        session,
        koperasi_id=koperasi_id,
        order_id=order_id,
        actor_user_id=actor_user_id,
        required_fulfillment_type=FulfillmentType.pickup,
    )
