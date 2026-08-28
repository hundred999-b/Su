import hashlib
import hmac
import json
import uuid
from decimal import Decimal, InvalidOperation

import requests
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .models import CryptoDeposit
from .services import get_asset_config
from ledger.wallet_service import credit_cash


# NOWPayments statuses which represent a completed payment.
FINISHED_STATUSES = {"finished"}

# Provider statuses which must never result in a wallet credit.
FAILED_STATUSES = {
    "failed",
    "expired",
    "refunded",
    "partially_refunded",
}

# Statuses that are still in progress and therefore do not credit the wallet.
PENDING_STATUSES = {
    "waiting",
    "confirming",
    "confirmed",
    "sending",
    "partially_paid",
}


def _headers():
    key = getattr(settings, "NOWPAYMENTS_API_KEY", "").strip()

    if not key:
        raise RuntimeError("NOWPAYMENTS_API_KEY is not configured.")

    return {
        "x-api-key": key,
        "Content-Type": "application/json",
    }


def _decimal(value, field_name):
    """
    Convert a provider value to Decimal without silently accepting
    malformed financial data.
    """
    try:
        value = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError(f"Invalid {field_name}.")

    if not value.is_finite():
        raise ValueError(f"Invalid {field_name}.")

    return value


def create_payment(
    *,
    user,
    amount,
    price_currency,
    pay_currency,
    order_id=None,
):
    """
    Create a NOWPayments payment and persist the provider information
    in CryptoDeposit.
    """
    amount = _decimal(amount, "payment amount")

    if amount <= 0:
        raise ValueError("Payment amount must be positive.")

    price_currency = str(price_currency or "").upper().strip()
    pay_currency = str(pay_currency or "").lower().strip()

    if not price_currency:
        raise ValueError("Price currency is required.")

    if not pay_currency:
        raise ValueError("Pay currency is required.")

    # Confirm ShopU knows the requested crypto asset.
    get_asset_config(pay_currency.upper())

    callback = getattr(settings, "NOWPAYMENTS_IPN_URL", "").strip()

    if not callback:
        raise RuntimeError("NOWPAYMENTS_IPN_URL is not configured.")

    order_ref = str(order_id or uuid.uuid4().hex)

    payload = {
        "price_amount": float(amount),
        "price_currency": price_currency.lower(),
        "pay_currency": pay_currency,
        "order_id": f"SHOPU-CRYPTO-{order_ref}",
        "order_description": f"ShopU wallet funding for user {user.id}",
        "ipn_callback_url": callback,
    }

    base_url = getattr(
        settings,
        "NOWPAYMENTS_BASE_URL",
        "https://api.nowpayments.io/v1",
    ).rstrip("/")

    try:
        response = requests.post(
            f"{base_url}/payment",
            headers=_headers(),
            json=payload,
            timeout=20,
        )
        response.raise_for_status()
        data = response.json()
    except requests.RequestException as exc:
        raise RuntimeError(
            f"NOWPayments payment request failed: {exc}"
        ) from exc
    except ValueError as exc:
        raise RuntimeError(
            "NOWPayments returned invalid JSON."
        ) from exc

    payment_id = data.get("payment_id")

    if not payment_id:
        raise ValueError(
            data.get("message")
            or "NOWPayments did not return a payment id."
        )

    provider_pay_amount = data.get("pay_amount")

    if provider_pay_amount is not None:
        provider_pay_amount = _decimal(
            provider_pay_amount,
            "NOWPayments pay_amount",
        )

        if provider_pay_amount <= 0:
            raise ValueError(
                "NOWPayments returned an invalid pay_amount."
            )

    deposit = CryptoDeposit.objects.create(
        user=user,
        asset=pay_currency.upper(),
        network="",
        amount=amount,
        address=data.get("pay_address") or "",
        tx_hash=None,
        provider="nowpayments",
        provider_payment_id=str(payment_id),
        price_currency=price_currency,
        pay_currency=pay_currency,
        pay_amount=provider_pay_amount,
        payment_url=data.get("invoice_url")
        or data.get("payin_extra_id")
        or "",
        metadata={
            "order_id": order_ref,
            "provider": data,
        },
    )

    return deposit


def _canonical_payload(payload):
    """
    NOWPayments signs the JSON payload after sorting its keys.
    """
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def verify_ipn_signature(payload, signature):
    """
    Verify NOWPayments IPN HMAC-SHA512 signature.
    """
    secret = getattr(settings, "NOWPAYMENTS_IPN_SECRET", "").strip()

    if not secret or not signature:
        return False

    expected = hmac.new(
        secret.encode("utf-8"),
        _canonical_payload(payload),
        hashlib.sha512,
    ).hexdigest()

    return hmac.compare_digest(
        expected.lower(),
        str(signature).strip().lower(),
    )


def _validate_finished_payment(deposit, payload):
    """
    Validate the important financial fields supplied by NOWPayments
    before a wallet credit is allowed.
    """

    payload_payment_id = str(
        payload.get("payment_id") or ""
    ).strip()

    if payload_payment_id != str(deposit.provider_payment_id):
        raise ValueError("NOWPayments payment ID mismatch.")

    payload_price_currency = str(
        payload.get("price_currency")
        or deposit.price_currency
        or ""
    ).upper().strip()

    if payload_price_currency != str(
        deposit.price_currency
    ).upper().strip():
        raise ValueError(
            "Crypto payment price currency mismatch."
        )

    payload_pay_currency = str(
        payload.get("pay_currency")
        or deposit.pay_currency
        or ""
    ).lower().strip()

    if payload_pay_currency != str(
        deposit.pay_currency
    ).lower().strip():
        raise ValueError(
            "Crypto payment currency mismatch."
        )

    # Validate the fiat-denominated order value.
    if payload.get("price_amount") is not None:
        price_amount = _decimal(
            payload["price_amount"],
            "NOWPayments price_amount",
        )

        if price_amount < deposit.amount:
            raise ValueError(
                "Crypto payment price amount is below "
                "the expected amount."
            )

    # Validate the expected crypto amount when available.
    expected_pay_amount = deposit.pay_amount

    if expected_pay_amount is not None:
        expected_pay_amount = _decimal(
            expected_pay_amount,
            "stored pay_amount",
        )

        if expected_pay_amount <= 0:
            raise ValueError(
                "Stored NOWPayments pay_amount is invalid."
            )

        # NOWPayments sends actually_paid when available.
        # For a finished payment, use the actual amount received.
        if payload.get("actually_paid") is not None:
            actually_paid = _decimal(
                payload["actually_paid"],
                "NOWPayments actually_paid",
            )

            if actually_paid < expected_pay_amount:
                raise ValueError(
                    "Crypto payment amount received is below "
                    "the expected amount."
                )

        # Some provider responses use pay_amount instead.
        elif payload.get("pay_amount") is not None:
            received_pay_amount = _decimal(
                payload["pay_amount"],
                "NOWPayments pay_amount",
            )

            if received_pay_amount < expected_pay_amount:
                raise ValueError(
                    "Crypto payment amount is below "
                    "the expected amount."
                )

    return True


@transaction.atomic
def process_ipn(payload):
    """
    Process one NOWPayments IPN.

    The row is locked while processing. A deposit which has already
    been confirmed is never credited again.
    """
    if not isinstance(payload, dict):
        raise ValueError("Invalid IPN payload.")

    payment_id = str(
        payload.get("payment_id") or ""
    ).strip()

    if not payment_id:
        raise ValueError("Missing payment_id.")

    status = str(
        payload.get("payment_status") or ""
    ).lower().strip()

    if not status:
        raise ValueError("Missing payment_status.")

    deposit = (
        CryptoDeposit.objects
        .select_for_update()
        .filter(
            provider="nowpayments",
            provider_payment_id=payment_id,
        )
        .first()
    )

    if not deposit:
        raise ValueError("Crypto payment not found.")

    # Store the latest provider event for audit/debugging.
    deposit.metadata = {
        **(deposit.metadata or {}),
        "last_ipn": payload,
    }

    # Idempotent behaviour:
    # if this exact deposit has already been confirmed, never credit again.
    if deposit.status == CryptoDeposit.CONFIRMED:
        deposit.save(update_fields=["metadata"])
        return deposit

    if status in FINISHED_STATUSES:
        _validate_finished_payment(
            deposit,
            payload,
        )

        # Wallet credit happens inside the same database transaction
        # as the deposit state transition.
        credit_cash(
            deposit.user,
            deposit.amount,
            deposit.price_currency,
            reference=f"CRYPTO:{payment_id}",
            metadata={
                "crypto_deposit_id": deposit.pk,
                "provider": "nowpayments",
                "payment_id": payment_id,
            },
        )

        deposit.status = CryptoDeposit.CONFIRMED
        deposit.confirmed_at = timezone.now()
        deposit.confirmations = max(
            deposit.confirmations,
            1,
        )

        tx_hash = (
            payload.get("payin_hash")
            or payload.get("outcome_tx_hash")
            or deposit.tx_hash
        )

        if tx_hash:
            deposit.tx_hash = str(tx_hash)

    elif status in FAILED_STATUSES:
        deposit.status = CryptoDeposit.FAILED

    elif status in PENDING_STATUSES:
        # Do not change a pending deposit into a failure.
        # We still save the latest provider payload.
        pass

    else:
        # Unknown provider status:
        # retain the current deposit state and audit the payload.
        pass

    deposit.save(
        update_fields=[
            "metadata",
            "status",
            "confirmed_at",
            "confirmations",
            "tx_hash",
        ]
    )

    return deposit
