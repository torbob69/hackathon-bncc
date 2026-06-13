import enum


class UserRole(str, enum.Enum):
    farmer = "farmer"
    manager = "manager"
    admin = "admin"
    distributor = "distributor"
    financing_partner = "financing_partner"
    platform_admin = "platform_admin"


class FarmerStatus(str, enum.Enum):
    pending = "pending"
    active = "active"


class IntakeStatus(str, enum.Enum):
    pending = "pending"
    confirmed = "confirmed"
    rejected = "rejected"
    cancelled = "cancelled"


class StockDirection(str, enum.Enum):
    in_ = "in"
    out = "out"


class OrderStatus(str, enum.Enum):
    pending = "pending"
    paid = "paid"
    fulfilled = "fulfilled"
    cancelled = "cancelled"


class FulfillmentType(str, enum.Enum):
    delivery = "delivery"
    pickup = "pickup"


class PaymentChannel(str, enum.Enum):
    qris = "qris"
    va = "va"


class PaymentStatus(str, enum.Enum):
    pending = "pending"
    paid = "paid"
    expired = "expired"
    failed = "failed"


class LedgerPool(str, enum.Enum):
    marginal_profit = "marginal_profit"
    loan = "loan"


class LedgerType(str, enum.Enum):
    sale_settlement = "sale_settlement"
    farmer_payment = "farmer_payment"
    platform_fee = "platform_fee"
    apbn_grant = "apbn_grant"
    loan_disbursement = "loan_disbursement"
    loan_repayment = "loan_repayment"
    refund = "refund"


class LedgerDirection(str, enum.Enum):
    credit = "credit"
    debit = "debit"


class LoanPurpose(str, enum.Enum):
    benih = "benih"
    pupuk = "pupuk"
    alat = "alat"


class LoanStatus(str, enum.Enum):
    pending = "pending"
    active = "active"
    past_due = "past_due"
    paid = "paid"
    rejected = "rejected"
    seized = "seized"


class InstallmentStatus(str, enum.Enum):
    unpaid = "unpaid"
    paid = "paid"
    late = "late"


class GrantStatus(str, enum.Enum):
    active = "active"
    revoked = "revoked"


class WebhookStatus(str, enum.Enum):
    received = "received"
    processed = "processed"
    duplicate = "duplicate"


class NotificationType(str, enum.Enum):
    intake_flagged = "intake_flagged"
    intake_confirmed = "intake_confirmed"
    intake_rejected = "intake_rejected"
    loan_status = "loan_status"
