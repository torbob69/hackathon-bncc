"""
Payment provider package.

Public surface:
    PaymentProvider      — abstract base class (import for type hints).
    get_payment_provider — factory; returns the correct provider based on
                           settings.MODE ('dev' → MockXenditProvider,
                           'prod' → XenditProvider).

Usage in services:
    from app.payments import get_payment_provider

    provider = get_payment_provider()
    result = await provider.create_disbursement(
        amount=principal,
        reference_id=loan.id,
        description="Loan disbursement",
    )

Never call Xendit or any payment API directly from a service or route —
always go through get_payment_provider() so that MODE=dev mocking stays intact
(CLAUDE.md §3.4, §8).
"""
from __future__ import annotations

from app.payments.base import PaymentProvider
from app.payments.mock import MockXenditProvider
from app.payments.xendit import XenditProvider


def get_payment_provider() -> PaymentProvider:
    """
    Return the appropriate PaymentProvider implementation based on settings.MODE.

    - 'dev'  → MockXenditProvider: deterministic, no external calls, instant
               responses.  Safe for local development and offline demos.
    - 'prod' → XenditProvider: real Xendit API.  Requires XENDIT_SECRET_KEY
               and XENDIT_CALLBACK_TOKEN to be set in the environment.

    The import of settings is deferred inside the function so that the module
    can be imported in test environments where settings might be partially
    configured.
    """
    from app.core.config import settings  # deferred to avoid circular import risk

    if settings.MODE == "dev":
        return MockXenditProvider()
    return XenditProvider()


__all__ = ["PaymentProvider", "get_payment_provider"]
