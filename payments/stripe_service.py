import uuid
from decimal import Decimal

import stripe
from django.conf import settings
from django.db import transaction

from .models import Payment


def _minor_units(amount, currency):
    from finance.models import SupportedCurrency
    cfg = SupportedCurrency.objects.filter(code=str(currency).upper()).first()
    decimals = cfg.decimal_places if cfg else 2
    return int((Decimal(str(amount)) * (Decimal("10") ** decimals)).quantize(Decimal("1")))


def initialize_stripe_payment(*, user, amount, currency, email=None, metadata=None):
    key = getattr(settings, "STRIPE_SECRET_KEY", "").strip()
    if not key:
        raise RuntimeError("STRIPE_SECRET_KEY is not configured.")
    currency = str(currency).upper().strip()
    allowed = getattr(settings, "STRIPE_ALLOWED_CURRENCIES", [])
    if allowed and currency not in allowed:
        raise ValueError("This currency is not enabled for Stripe funding.")
    amount = Decimal(str(amount))
    if amount <= 0:
        raise ValueError("Payment amount must be positive.")
    email = (email or getattr(user, "email", "")).strip()
    if not email:
        raise ValueError("A valid email address is required for payment.")
    success_url = getattr(settings, "STRIPE_SUCCESS_URL", "").strip()
    cancel_url = getattr(settings, "STRIPE_CANCEL_URL", "").strip()
    if not success_url or not cancel_url:
        raise RuntimeError("STRIPE_SUCCESS_URL and STRIPE_CANCEL_URL are required.")

    reference = f"SHOPU-STRIPE-{uuid.uuid4().hex.upper()}"
    from .services import create_payment
    payment = create_payment(
        user=user,
        provider="stripe",
        provider_reference=reference,
        amount=amount,
        currency=currency,
        metadata={"email": email, **(metadata or {})},
    )
    stripe.api_key = key
    session = stripe.checkout.Session.create(
        mode="payment",
        customer_email=email,
        client_reference_id=reference,
        line_items=[{
            "price_data": {
                "currency": currency.lower(),
                "product_data": {"name": "ShopU Wallet Funding"},
                "unit_amount": _minor_units(amount, currency),
            },
            "quantity": 1,
        }],
        metadata={"shopu_payment_id": str(payment.id), "shopu_reference": reference, **(metadata or {})},
        success_url=success_url,
        cancel_url=cancel_url,
    )
    payment.authorization_url = session.url or ""
    payment.access_code = session.id
    payment.metadata = {**payment.metadata, "stripe_session_id": session.id}
    payment.save(update_fields=["authorization_url", "access_code", "metadata"])
    return payment


@transaction.atomic
def handle_stripe_webhook(payload, signature):
    secret = getattr(settings, "STRIPE_WEBHOOK_SECRET", "").strip()
    if not secret:
        raise RuntimeError("STRIPE_WEBHOOK_SECRET is not configured.")

    if not signature:
        raise ValueError("Stripe signature is required.")

    stripe.api_key = getattr(settings, "STRIPE_SECRET_KEY", "").strip()
    event = stripe.Webhook.construct_event(payload, signature, secret)

    if event.get("type") != "checkout.session.completed":
        return False

    session = event.get("data", {}).get("object") or {}

    if session.get("payment_status") != "paid":
        return False

    metadata = session.get("metadata") or {}
    reference = (
        session.get("client_reference_id")
        or metadata.get("shopu_reference")
    )

    if not reference:
        return False

    payment = Payment.objects.select_for_update().filter(
        provider="stripe",
        provider_reference=reference,
    ).first()

    if not payment:
        return False

    # The Stripe session must identify the exact ShopU payment.
    shopu_payment_id = metadata.get("shopu_payment_id")
    if shopu_payment_id is not None and str(shopu_payment_id) != str(payment.pk):
        raise ValueError("Stripe ShopU payment mismatch.")

    metadata_reference = metadata.get("shopu_reference")
    if metadata_reference is not None and metadata_reference != payment.provider_reference:
        raise ValueError("Stripe reference mismatch.")

    # If we already completed this payment, safely acknowledge the
    # duplicate webhook without touching the wallet again.
    if payment.status == Payment.SUCCEEDED:
        return True

    if payment.status != Payment.PENDING:
        raise ValueError("Stripe payment is not pending.")

    if int(session.get("amount_total") or 0) != _minor_units(
        payment.amount,
        payment.currency,
    ):
        raise ValueError("Stripe amount mismatch.")

    if str(session.get("currency") or "").upper() != payment.currency:
        raise ValueError("Stripe currency mismatch.")

    from .services import mark_succeeded

    mark_succeeded(
        payment.id,
        provider_reference=reference,
    )

    return True
