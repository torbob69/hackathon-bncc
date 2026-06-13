from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.enums import FulfillmentType, OrderStatus, PaymentChannel, PaymentStatus


class CatalogItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    koperasi_id: int
    name: str
    unit: str
    pihps_price: Decimal
    current_stock_kg: Decimal
    cold_storage_location: str | None
    created_at: datetime


class OrderItemCreate(BaseModel):
    commodity_id: int = Field(..., gt=0)
    weight_kg: Decimal = Field(..., gt=0)


class OrderCreate(BaseModel):
    koperasi_id: int = Field(..., gt=0)
    fulfillment_type: FulfillmentType
    delivery_address: str | None = Field(default=None, max_length=1000)
    items: list[OrderItemCreate] = Field(..., min_length=1)

    @model_validator(mode="after")
    def validate_delivery_address(self) -> "OrderCreate":
        if self.fulfillment_type == FulfillmentType.delivery and not self.delivery_address:
            raise ValueError("delivery_address is required for delivery orders.")
        return self


class OrderItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    order_id: int
    koperasi_id: int
    commodity_id: int
    weight_kg: Decimal
    price_per_kg: Decimal
    line_total: Decimal


class OrderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    koperasi_id: int
    distributor_id: int
    status: OrderStatus
    fulfillment_type: FulfillmentType
    delivery_address: str | None
    subtotal: Decimal
    platform_fee: Decimal
    total: Decimal
    xendit_invoice_id: str | None
    payment_channel: PaymentChannel | None
    payment_status: PaymentStatus | None
    pickup_qr_token: str | None
    created_at: datetime


class OrderDetailOut(OrderOut):
    items: list[OrderItemOut] = Field(default_factory=list)
    payment_url: str | None = None


class MockInvoiceWebhookRequest(BaseModel):
    event_id: str = Field(..., min_length=3, max_length=128)
    invoice_id: str = Field(..., min_length=3, max_length=255)
    status: PaymentStatus = PaymentStatus.paid


class WebhookProcessOut(BaseModel):
    event_id: str
    status: str
    order_id: int | None = None
    detail: str


class PickupVerifyRequest(BaseModel):
    token: str = Field(..., min_length=20)


class FulfillmentOut(BaseModel):
    order: OrderDetailOut
    released_stock_movements: int
