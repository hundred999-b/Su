import hashlib
import hmac
import json
import uuid
from decimal import Decimal, InvalidOperation

import requests
from django.conf import settings
from django.db import transaction

from .models import Payment
from ledger.wallet_service import credit_cash

PAYSTACK_BASE = "https://api.paystack.co"


def _paystack_headers():
    key = getattr(settings, "PAYSTACK_SECRET_KEY", "").strip()
    if not key:
        raise RuntimeError("PAYSTACK_SECRET_KEY is not configured.")
    return {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }


def _amount_subunit(amount, currency):
    from finance.models import SupportedCurrency
    cfg = SupportedCurrency.objects.filter(code=str(currency).upper()).first()
    decimals = cfg.decimal_places if cfg else 2
    return int((Decimal(str(amount)) * (Decimal("10") ** decimals)).quantize(Decimal("1")))


@transaction.atomic
def create_payment(
    *,
    user,
    provider,
    provider_reference,
    amount,
    currency="USD",
    idempotency_key=None,
    metadata=None,
):
    amount = Decimal(str(amount))
    if amount <= 0:
        raise ValueError("Payment amount must be positive.")
    key = idempotency_key or provider_reference
    payment, created = Payment.objects.get_or_create(
        idempotency_key=key,
        defaults={
            "user": user,
            "provider": provider,
            "provider_reference": provider_reference,
            "amount": amount,
            "currency": currency.upper(),
            "status": Payment.PENDING,
            "metadata": metadata or {},
        },
    )
    if not created:
        if payment.provider_reference != provider_reference:
            raise ValueError(
                "Idempotency key is already associated with another payment."
            )
        return payment
    return payment


def initialize_paystack_payment(*, user, amount, currency=None, email=None, metadata=None):
    currency = (currency or getattr(settings, "PAYSTACK_CURRENCY", "")).upper()
    if not currency:
        raise ValueError("A currency is required for Paystack funding.")
    allowed = getattr(settings, "PAYSTACK_ALLOWED_CURRENCIES", [currency])
    if allowed and currency not in allowed:
        raise ValueError("This currency is not enabled for Paystack funding.")

    try:
        amount = Decimal(str(amount))
    except InvalidOperation:
        raise ValueError("Invalid payment amount.")
    if amount <= 0:
        raise ValueError("Payment amount must be positive.")

    email = (email or getattr(user, "email", "")).strip()
    if not email:
        raise ValueError("A valid email address is required for payment.")

    reference = f"SHOPU-{uuid.uuid4().hex.upper()}"
    payment = create_payment(
        user=user,
        provider="paystack",
        provider_reference=reference,
        amount=amount,
        currency=currency,
        metadata={"email": email, **(metadata or {})},
    )

    payload = {
        "email": email,
        "amount": _amount_subunit(amount, currency),
        "currency": currency,
        "reference": reference,
        "metadata": json.dumps({
            "shopu_payment_id": payment.id,
            "shopu_user_id": user.id,
            **(metadata or {}),
        }),
    }
    callback_url = getattr(settings, "PAYSTACK_CALLBACK_URL", "").strip()
    if callback_url:
        payload["callback_url"] = callback_url

    response = requests.post(
        f"{PAYSTACK_BASE}/transaction/initialize",
        headers=_paystack_headers(),
        json=payload,
        timeout=20,
    )
    response.raise_for_status()
    data = response.json()
    if not data.get("status") or not data.get("data"):
        raise ValueError(data.get("message") or "Paystack initialization failed.")

    result = data["data"]
    payment.authorization_url = result.get("authorization_url", "")
    payment.access_code = result.get("access_code", "")
    payment.metadata = {
        **payment.metadata,
        "paystack": {
            "authorization_url": payment.authorization_url,
            "access_code": payment.access_code,
        },
    }
    payment.save(update_fields=["authorization_url", "access_code", "metadata"])
    return payment


def _verify_paystack_reference(reference):
    response = requests.get(
        f"{PAYSTACK_BASE}/transaction/verify/{reference}",
        headers=_paystack_headers(),
        timeout=20,
    )
    response.raise_for_status()
    return response.json()


@transaction.atomic
def mark_succeeded(payment_id, provider_reference=None):
    payment = Payment.objects.select_for_update().get(pk=payment_id)
    if payment.status == Payment.SUCCEEDED:
        return payment
    if payment.status not in (Payment.PENDING,):
        raise ValueError("Only pending payments can succeed.")
    if provider_reference and payment.provider_reference != provider_reference:
        raise ValueError("Provider reference mismatch.")

    is_gift_card_purchase = (payment.metadata or {}).get("purpose") == "gift_card"
    if not is_gift_card_purchase:
        credit_cash(
            payment.user,
            payment.amount,
            payment.currency,
            reference=f"PAYMENT:{payment.provider_reference}",
            metadata={
                "payment_id": payment.pk,
                "provider": payment.provider,
            },
        )
    payment.status = Payment.SUCCEEDED
    payment.save(update_fields=["status"])
    if is_gift_card_purchase:
        from giftcards.models import GiftCardPurchase
        from giftcards.services import complete_gift_card_purchase
        purchase_id = (payment.metadata or {}).get("gift_card_purchase_id")
        if purchase_id:
            complete_gift_card_purchase(int(purchase_id))
        else:
            gift_card_id = (payment.metadata or {}).get("gift_card_id")
            purchase = GiftCardPurchase.objects.filter(
                payment=payment, gift_card_id=gift_card_id, status=GiftCardPurchase.PENDING
            ).first() if gift_card_id else None
            if purchase:
                complete_gift_card_purchase(purchase.id)
    return payment


@transaction.atomic
def verify_paystack_payment(reference):
    payment = Payment.objects.select_for_update().filter(
        provider="paystack",
        provider_reference=reference,
    ).first()
    if not payment:
        raise ValueError("Payment not found.")

    result = _verify_paystack_reference(reference)
    data = result.get("data") or {}
    status = data.get("status")

    expected_amount = _amount_subunit(payment.amount, payment.currency)
    if int(data.get("amount") or 0) != expected_amount:
        raise ValueError("Paystack amount does not match the ShopU payment.")
    if str(data.get("currency", "")).upper() != payment.currency.upper():
        raise ValueError("Paystack currency does not match the ShopU payment.")

    if status == "success":
        mark_succeeded(payment.id, provider_reference=reference)
    elif status in ("failed", "abandoned", "reversed"):
        payment.status = Payment.FAILED
        payment.save(update_fields=["status"])
    return payment, data


def verify_paystack_signature(raw_body, signature):
    secret = getattr(settings, "PAYSTACK_SECRET_KEY", "").strip()
    if not secret or not signature:
        return False
    expected = hmac.new(
        secret.encode(), raw_body, hashlib.sha512
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


def initialize_payment(*, user, amount, currency, email=None, provider=None, metadata=None):
    """Route a fiat payment through an enabled gateway without hard-coding a country."""
    from finance.models import PaymentGatewayConfig
    currency = str(currency).upper().strip()
    requested = (provider or "").strip().lower()
    configs = PaymentGatewayConfig.objects.filter(enabled=True).order_by("priority", "provider")
    if requested:
        configs = configs.filter(provider=requested)
    for config in configs:
        currencies = {str(c).upper() for c in (config.supported_currencies or [])}
        if currencies and currency not in currencies:
            continue
        if config.provider == "stripe":
            from .stripe_service import initialize_stripe_payment
            return initialize_stripe_payment(user=user, amount=amount, currency=currency, email=email, metadata=metadata)
        if config.provider == "paystack":
            return initialize_paystack_payment(user=user, amount=amount, currency=currency, email=email, metadata=metadata)
    raise ValueError(f"No enabled payment gateway is configured for {currency}.")
