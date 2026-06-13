from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.commodities import Commodity
from app.models.enums import (
    FulfillmentType,
    LedgerDirection,
    LedgerPool,
    LedgerType,
    OrderStatus,
    PaymentChannel,
    PaymentStatus,
    WebhookStatus,
)
from app.models.orders import Order, OrderItem
from app.models.webhooks import XenditWebhookEvent
from app.payments import get_payment_provider
from app.services.audit import write_audit
from app.services.ledger import post_ledger_entry
from app.services.qr import sign_qr_payload

PLATFORM_FEE_RATE = Decimal("0.02")
QRIS_LIMIT = Decimal("10000000.00")


class OrderNotFound(Exception):
    pass


class OrderStateError(Exception):
    pass


class CommodityUnavailable(Exception):
    pass


class WebhookIgnored(Exception):
    pass


@dataclass(frozen=True)
class CheckoutResult:
    order: Order
    items: list[OrderItem]
    payment_url: str | None


@dataclass(frozen=True)
class WebhookResult:
    event_id: str
    status: str
    order_id: int | None
    detail: str


def _money(value: Decimal) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _weight(value: Decimal) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)


def select_payment_channel(total: Decimal) -> PaymentChannel:
    return PaymentChannel.qris if total <= QRIS_LIMIT else PaymentChannel.va


async def list_catalog(
    session: AsyncSession,
    *,
    koperasi_id: int | None = None,
    in_stock_only: bool = True,
) -> list[Commodity]:
    q = select(Commodity).order_by(Commodity.koperasi_id, Commodity.name)
    if koperasi_id is not None:
        q = q.where(Commodity.koperasi_id == koperasi_id)
    if in_stock_only:
        q = q.where(Commodity.current_stock_kg > Decimal("0"))
    result = await session.execute(q)
    return list(result.scalars().all())


async def create_order(
    session: AsyncSession,
    *,
    distributor_id: int,
    koperasi_id: int,
    fulfillment_type: FulfillmentType,
    delivery_address: str | None,
    items: list[tuple[int, Decimal]],
) -> CheckoutResult:
    commodity_ids = [commodity_id for commodity_id, _ in items]
    result = await session.execute(
        select(Commodity).where(
            Commodity.koperasi_id == koperasi_id,
            Commodity.id.in_(commodity_ids),
        )
    )
    commodities = {commodity.id: commodity for commodity in result.scalars().all()}
    if len(commodities) != len(set(commodity_ids)):
        raise CommodityUnavailable("One or more commodities are not available in this koperasi.")

    order_items: list[OrderItem] = []
    subtotal = Decimal("0.00")
    for commodity_id, requested_weight in items:
        commodity = commodities[commodity_id]
        weight = _weight(requested_weight)
        line_total = _money(weight * Decimal(str(commodity.pihps_price)))
        subtotal += line_total
        order_items.append(
            OrderItem(
                koperasi_id=koperasi_id,
                commodity_id=commodity_id,
                weight_kg=weight,
                price_per_kg=Decimal(str(commodity.pihps_price)),
                line_total=line_total,
            )
        )

    subtotal = _money(subtotal)
    platform_fee = _money(subtotal * PLATFORM_FEE_RATE)
    total = _money(subtotal + platform_fee)
    payment_channel = select_payment_channel(total)

    order = Order(
        koperasi_id=koperasi_id,
        distributor_id=distributor_id,
        status=OrderStatus.pending,
        fulfillment_type=fulfillment_type,
        delivery_address=delivery_address,
        subtotal=subtotal,
        platform_fee=platform_fee,
        total=total,
        payment_channel=payment_channel,
        payment_status=PaymentStatus.pending,
    )
    session.add(order)
    await session.flush()

    for item in order_items:
        item.order_id = order.id
        session.add(item)
    await session.flush()

    provider = get_payment_provider()
    invoice = await provider.create_invoice(
        amount=total,
        reference_id=str(order.id),
        payment_channel=payment_channel.value,
        description=f"KoperaLink order #{order.id}",
        split={"platform_fee": str(platform_fee), "koperasi_id": koperasi_id},
    )
    order.xendit_invoice_id = invoice["invoice_id"]
    provider_status = invoice.get("status")
    payment_url = invoice.get("payment_url")

    await write_audit(
        session,
        actor_user_id=distributor_id,
        koperasi_id=koperasi_id,
        action="order_created",
        entity_type="order",
        entity_id=order.id,
        after={
            "subtotal": subtotal,
            "platform_fee": platform_fee,
            "total": total,
            "payment_channel": payment_channel.value,
            "xendit_invoice_id": order.xendit_invoice_id,
        },
    )

    if provider_status == "paid":
        await process_invoice_settlement(
            session,
            event_id=f"mock-invoice-paid-{order.xendit_invoice_id}",
            invoice_id=order.xendit_invoice_id,
            payload={
                "source": "mock_provider",
                "status": "paid",
                "order_id": order.id,
            },
        )
    await session.flush()

    return CheckoutResult(order=order, items=order_items, payment_url=payment_url)


async def get_order_detail(
    session: AsyncSession,
    *,
    order_id: int,
    distributor_id: int | None = None,
    koperasi_id: int | None = None,
) -> tuple[Order, list[OrderItem]]:
    q = select(Order).where(Order.id == order_id)
    if distributor_id is not None:
        q = q.where(Order.distributor_id == distributor_id)
    if koperasi_id is not None:
        q = q.where(Order.koperasi_id == koperasi_id)
    result = await session.execute(q)
    order = result.scalar_one_or_none()
    if order is None:
        raise OrderNotFound(f"Order {order_id} not found.")

    item_result = await session.execute(
        select(OrderItem)
        .where(OrderItem.order_id == order.id, OrderItem.koperasi_id == order.koperasi_id)
        .order_by(OrderItem.id)
    )
    return order, list(item_result.scalars().all())


async def list_orders_for_distributor(
    session: AsyncSession,
    *,
    distributor_id: int,
) -> list[Order]:
    result = await session.execute(
        select(Order)
        .where(Order.distributor_id == distributor_id)
        .order_by(Order.created_at.desc())
    )
    return list(result.scalars().all())


async def list_orders_for_koperasi(
    session: AsyncSession,
    *,
    koperasi_id: int,
    status: OrderStatus | None = None,
) -> list[Order]:
    q = select(Order).where(Order.koperasi_id == koperasi_id).order_by(Order.created_at.desc())
    if status is not None:
        q = q.where(Order.status == status)
    result = await session.execute(q)
    return list(result.scalars().all())


async def process_invoice_settlement(
    session: AsyncSession,
    *,
    event_id: str,
    invoice_id: str,
    payload: dict,
) -> WebhookResult:
    insert_stmt = (
        pg_insert(XenditWebhookEvent)
        .values(
            event_id=event_id,
            event_type="invoice.paid",
            reference_type="order",
            payload=payload,
            status=WebhookStatus.received,
        )
        .on_conflict_do_nothing(index_elements=["event_id"])
        .returning(XenditWebhookEvent.id)
    )
    inserted = (await session.execute(insert_stmt)).scalar_one_or_none()
    if inserted is None:
        return WebhookResult(event_id=event_id, status="duplicate", order_id=None, detail="Event already processed.")

    order_result = await session.execute(
        select(Order).where(Order.xendit_invoice_id == invoice_id).with_for_update()
    )
    order = order_result.scalar_one_or_none()
    if order is None:
        event = await session.get(XenditWebhookEvent, inserted)
        event.status = WebhookStatus.processed
        event.processed_at = datetime.now(UTC)
        return WebhookResult(event_id=event_id, status="ignored", order_id=None, detail="Invoice does not match an order.")

    event = await session.get(XenditWebhookEvent, inserted)
    event.reference_id = order.id

    if payload.get("status") not in (None, "paid", "PAID"):
        event.status = WebhookStatus.processed
        event.processed_at = datetime.now(UTC)
        raise WebhookIgnored("Only paid invoice events settle orders.")

    order.payment_status = PaymentStatus.paid
    order.status = OrderStatus.paid

    await post_ledger_entry(
        session,
        koperasi_id=order.koperasi_id,
        pool=LedgerPool.marginal_profit,
        type=LedgerType.sale_settlement,
        amount=Decimal(str(order.total)),
        direction=LedgerDirection.credit,
        reference_type="order",
        reference_id=order.id,
        external_idempotency_key=f"invoice-{invoice_id}-gross",
    )
    await post_ledger_entry(
        session,
        koperasi_id=order.koperasi_id,
        pool=LedgerPool.marginal_profit,
        type=LedgerType.platform_fee,
        amount=Decimal(str(order.platform_fee)),
        direction=LedgerDirection.debit,
        reference_type="order",
        reference_id=order.id,
        external_idempotency_key=f"invoice-{invoice_id}-platform-fee",
    )

    if order.fulfillment_type == FulfillmentType.pickup and order.pickup_qr_token is None:
        order.pickup_qr_token = sign_qr_payload(
            payload_type="pickup",
            payload={
                "order_id": order.id,
                "koperasi_id": order.koperasi_id,
                "distributor_id": order.distributor_id,
            },
        )

    await write_audit(
        session,
        actor_user_id=None,
        koperasi_id=order.koperasi_id,
        action="order_paid",
        entity_type="order",
        entity_id=order.id,
        after={
            "payment_status": PaymentStatus.paid.value,
            "status": OrderStatus.paid.value,
            "xendit_invoice_id": invoice_id,
            "event_id": event_id,
        },
    )

    event.status = WebhookStatus.processed
    event.processed_at = datetime.now(UTC)
    await session.flush()
    return WebhookResult(event_id=event_id, status="processed", order_id=order.id, detail="Order settled.")
