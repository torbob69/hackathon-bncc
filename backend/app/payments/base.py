"""
Abstract PaymentProvider interface.

All payment operations in the platform MUST go through this interface so that
MODE=dev can use MockXenditProvider without any external calls, and MODE=prod
transparently swaps in the real XenditProvider.

Rules (CLAUDE.md §3.4 / §8):
- Never call Xendit or any external payment API directly from a service or
  route — always obtain the provider via get_payment_provider() and call it
  through this interface.
- create_disbursement is used for loan disbursements and farmer harvest payments.
  It returns a dict with at minimum 'disbursement_id' and 'status'.
- create_invoice is used for marketplace checkout (orders). It returns a dict
  with at minimum 'invoice_id', 'status', and 'payment_url'.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from decimal import Decimal


class PaymentProvider(ABC):
    """
    Abstract base class defining the payment provider contract.

    All concrete implementations (MockXenditProvider, XenditProvider) must
    implement every abstract method below.
    """

    # ------------------------------------------------------------------
    # Disbursement — used for loan payouts and farmer harvest payments
    # ------------------------------------------------------------------

    @abstractmethod
    async def create_disbursement(
        self,
        *,
        amount: Decimal,
        reference_id: int,
        description: str,
    ) -> dict:
        """
        Initiate a money transfer to a beneficiary (farmer or loan recipient).

        Parameters:
            amount        — Exact amount to disburse (Decimal, never float).
            reference_id  — PK of the referencing domain row (e.g. loan.id).
                            Used to build a unique external reference so the
                            provider can detect duplicate requests.
            description   — Human-readable purpose label shown on the transfer.

        Returns a dict containing at minimum:
            {
                'disbursement_id': str,   # provider-assigned ID (or mock ID)
                'status':          str,   # 'completed' | 'pending' | 'failed'
            }

        Raises:
            NotImplementedError — stub implementations that are not yet wired.
            Any provider-specific exception for real failures.
        """

    # ------------------------------------------------------------------
    # Invoice — used for marketplace orders (checkout)
    # ------------------------------------------------------------------

    @abstractmethod
    async def create_invoice(
        self,
        *,
        amount: Decimal,
        reference_id: str,
        payment_channel: str,
        **kw,
    ) -> dict:
        """
        Create a payment invoice for a marketplace order.

        Parameters:
            amount          — Total invoice amount (Decimal).
            reference_id    — Unique order reference string (e.g. str(order.id)).
            payment_channel — 'qris' for amounts <= Rp 10,000,000;
                              'va' for larger amounts. Mock ignores this.
            **kw            — Additional provider-specific keyword arguments
                              (e.g. payer_email, description, split_params).

        Returns a dict containing at minimum:
            {
                'invoice_id':   str,   # provider-assigned invoice ID
                'status':       str,   # 'paid' | 'pending' | 'expired'
                'payment_url':  str,   # URL the payer visits to complete payment
            }

        Raises:
            NotImplementedError — stub implementations.
        """
