"""
XenditProvider — production Xendit integration stub.

Selected automatically when settings.MODE == 'prod'.

Current status: STUB — methods raise NotImplementedError with a TODO comment.
Wire up with the httpx-based Xendit API calls once the real credentials and
split-payment mechanism (Xendit for Platforms managed sub-accounts vs
invoice-level fees) are finalised.

Reference (CLAUDE.md §3.4):
  - Sales: Xendit direct + split payment — 1-2% platform fee split off,
    remainder to the koperasi's Xendit account.
  - QRIS cap: orders <= Rp 10,000,000/day use QRIS; larger orders fall back
    to Virtual Account.
  - Disbursement: Xendit Disbursement API, mirrored in ledger_entries.

TODO:
  1. Import httpx and app.core.config.settings for XENDIT_SECRET_KEY.
  2. Implement create_disbursement using POST /disbursements v1 or v2.
  3. Implement create_invoice using POST /v2/invoices with split_params.
  4. Add webhook signature verification using XENDIT_CALLBACK_TOKEN.
"""
from __future__ import annotations

from decimal import Decimal

from app.payments.base import PaymentProvider


class XenditProvider(PaymentProvider):
    """
    Production Xendit payment provider.

    STUB — not yet implemented.  All methods raise NotImplementedError.
    Deploy with MODE=dev (MockXenditProvider) until this stub is wired.
    """

    async def create_disbursement(
        self,
        *,
        amount: Decimal,
        reference_id: int,
        description: str,
    ) -> dict:
        # TODO: Implement real Xendit Disbursement API call.
        #   POST https://api.xendit.co/disbursements
        #   Headers: Authorization: Basic <base64(XENDIT_SECRET_KEY:)>
        #   Body: {
        #     "external_id": f"loan-disb-{reference_id}",
        #     "amount": float(amount),
        #     "bank_code": ...,
        #     "account_holder_name": ...,
        #     "account_number": ...,
        #     "description": description,
        #   }
        #   Return: {'disbursement_id': response['id'], 'status': response['status']}
        raise NotImplementedError(
            "XenditProvider.create_disbursement is not yet implemented. "
            "Use MODE=dev for mock disbursements. "
            "See xendit.py TODO comments for implementation guidance."
        )

    async def create_invoice(
        self,
        *,
        amount: Decimal,
        reference_id: str,
        payment_channel: str,
        **kw,
    ) -> dict:
        # TODO: Implement real Xendit Invoice API call with split payment.
        #   POST https://api.xendit.co/v2/invoices
        #   Headers: Authorization: Basic <base64(XENDIT_SECRET_KEY:)>
        #   Body: {
        #     "external_id": reference_id,
        #     "amount": float(amount),
        #     "payment_methods": [payment_channel.upper()],  # "QRIS" or "VIRTUAL_ACCOUNT"
        #     ... plus split_params for platform fee once mechanism is finalised ...
        #   }
        #   QRIS cap: if amount > 10_000_000 and payment_channel == 'qris',
        #             fall back to 'va' before calling.
        #   Return: {'invoice_id': response['id'], 'status': response['status'],
        #            'payment_url': response['invoice_url']}
        raise NotImplementedError(
            "XenditProvider.create_invoice is not yet implemented. "
            "Use MODE=dev for mock invoices. "
            "See xendit.py TODO comments for implementation guidance."
        )
