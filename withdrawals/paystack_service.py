import hashlib
import hmac
import uuid
from decimal import Decimal

import requests
from django.conf import settings
from django.db import transaction

from .models import WithdrawalRequest
from .services import (
    mark_withdrawal_processing,
    complete_withdrawal,
    fail_withdrawal,
)

PAYSTACK_BASE = "https://api.paystack.co"


def _headers():
    secret = getattr(settings, "PAYSTACK_SECRET_KEY", "").strip()
    if not secret:
        raise RuntimeError("PAYSTACK_SECRET_KEY is not configured.")
    return {
        "Authorization": f"Bearer {secret}",
        "Content-Type": "application/json",
    }


def _request(method, path, **kwargs):
    response = requests.request(
        method,
        f"{PAYSTACK_BASE}{path}",
        headers=_headers(),
        timeout=30,
        **kwargs,
    )
    response.raise_for_status()
    payload = response.json()

    if not payload.get("status"):
        raise ValueError(payload.get("message") or "Paystack request failed.")

    return payload


def _minor_units(amount):
    return int(
        (Decimal(str(amount)) * Decimal("100")).quantize(Decimal("1"))
    )


def create_transfer_recipient(
    *,
    name,
    account_number,
    bank_code,
    currency="NGN",
    email="",
):
    payload = {
        "type": "nuban",
        "name": name,
        "account_number": account_number,
        "bank_code": bank_code,
        "currency": currency.upper(),
    }

    if email:
        payload["email"] = email

    result = _request(
        "POST",
        "/transferrecipient",
        json=payload,
    )

    data = result["data"]

    return {
        "recipient_code": data["recipient_code"],
        "currency": data.get("currency"),
        "name": data.get("name"),
        "details": data.get("details") or {},
    }


def initiate_transfer(*, withdrawal, recipient_code):
    reference = (
        f"shopu-{withdrawal.pk}-{uuid.uuid4().hex[:24]}"
    ).lower()[:50]

    payload = {
        "source": "balance",
        "amount": _minor_units(withdrawal.amount),
        "recipient": recipient_code,
        "reference": reference,
        "reason": f"ShopU marketplace withdrawal #{withdrawal.pk}",
    }

    result = _request(
        "POST",
        "/transfer",
        json=payload,
    )

    data = result["data"]

    mark_withdrawal_processing(
        withdrawal.pk,
        provider_reference=data.get("reference") or reference,
        provider_recipient=recipient_code,
        metadata={
            "paystack_transfer_id": data.get("id"),
            "paystack_transfer_code": data.get("transfer_code"),
            "paystack_status": data.get("status"),
        },
    )

    return data


def verify_signature(raw_body, signature):
    secret = getattr(settings, "PAYSTACK_SECRET_KEY", "").strip()

    if not secret or not signature:
        return False

    expected = hmac.new(
        secret.encode(),
        raw_body,
        hashlib.sha512,
    ).hexdigest()

    return hmac.compare_digest(expected, signature)


@transaction.atomic
def handle_transfer_webhook(payload):
    event = payload.get("event")
    data = payload.get("data") or {}
    reference = data.get("reference")

    if not reference:
        return False

    withdrawal = (
        WithdrawalRequest.objects
        .select_for_update()
        .filter(
            provider=WithdrawalRequest.PROVIDER_PAYSTACK,
            provider_reference=reference,
        )
        .first()
    )

    if not withdrawal:
        return False

    if event == "transfer.success":
        complete_withdrawal(
            withdrawal.pk,
            provider_reference=reference,
            metadata={"paystack_event": event},
        )
        return True

    if event in ("transfer.failed", "transfer.reversed"):
        fail_withdrawal(
            withdrawal.pk,
            reason=data.get("reason") or "Paystack transfer failed.",
            metadata={"paystack_event": event},
        )
        return True

    return False
