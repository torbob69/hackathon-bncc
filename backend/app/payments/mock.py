"""
MockXenditProvider — deterministic, zero-external-call payment provider.

Selected automatically when settings.MODE == 'dev'.

Behaviour:
  - create_disbursement: returns instant 'completed' with a deterministic
    mock disbursement ID derived from the reference_id.  No network call,
    no QRIS cap, no Xendit credentials required.
  - create_invoice: returns an instantly 'paid' invoice with a deterministic
    invoice ID and a fake payment URL.  Allows the full order/checkout flow
    to be demoed entirely offline.

These deterministic IDs mean the same reference_id always produces the same
mock ID — which is intentional for test repeatability and idempotency checks.
"""
from __future__ import annotations

import logging
from decimal import Decimal

from app.payments.base import PaymentProvider

logger = logging.getLogger(__name__)


class MockXenditProvider(PaymentProvider):
    """
    Deterministic mock provider for development and offline demos.

    All methods complete synchronously (no await on I/O) and return
    pre-determined dicts that mirror the shape of real Xendit responses
    so the service layer does not need any branching on MODE.
    """

    async def create_disbursement(
        self,
        *,
        amount: Decimal,
        reference_id: int,
        description: str,
    ) -> dict:
        """
        Return a fake-but-deterministic disbursement result.

        The disbursement_id follows the pattern 'mock-disb-{reference_id}'
        so callers can always predict and assert the value in tests.

        Returns:
            {
                'disbursement_id': 'mock-disb-<reference_id>',
                'status':          'completed',
                'amount':          <amount as str>,
                'description':     <description>,
            }
        """
        disbursement_id = f"mock-disb-{reference_id}"
        logger.info(
            "MockXenditProvider.create_disbursement: amount=%s reference_id=%d "
            "disbursement_id=%s",
            amount,
            reference_id,
            disbursement_id,
        )
        return {
            "disbursement_id": disbursement_id,
            "status": "completed",
            "amount": str(amount),
            "description": description,
        }

    async def create_invoice(
        self,
        *,
        amount: Decimal,
        reference_id: str,
        payment_channel: str,
        **kw,
    ) -> dict:
        """
        Return a fake-but-deterministic invoice result, instantly 'paid'.

        The invoice_id follows the pattern 'mock-inv-{reference_id}'.
        No QRIS cap is applied — the mock accepts any amount on any channel.

        Returns:
            {
                'invoice_id':   'mock-inv-<reference_id>',
                'status':       'paid',
                'payment_url':  'https://mock.xendit.test/pay/mock-inv-<reference_id>',
                'amount':       <amount as str>,
                'channel':      <payment_channel>,
            }
        """
        invoice_id = f"mock-inv-{reference_id}"
        payment_url = f"https://mock.xendit.test/pay/{invoice_id}"
        logger.info(
            "MockXenditProvider.create_invoice: amount=%s reference_id=%s "
            "channel=%s invoice_id=%s",
            amount,
            reference_id,
            payment_channel,
            invoice_id,
        )
        return {
            "invoice_id": invoice_id,
            "status": "paid",
            "payment_url": payment_url,
            "amount": str(amount),
            "channel": payment_channel,
        }
