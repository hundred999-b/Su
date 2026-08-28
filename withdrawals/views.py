import json

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .models import WithdrawalRequest
from .paystack_service import (
    create_transfer_recipient,
    initiate_transfer,
    handle_transfer_webhook,
    verify_signature,
)
from .services import create_withdrawal


@login_required
@require_POST
def create_paystack_recipient(request):
    try:
        body = json.loads(request.body.decode("utf-8"))

        name = str(body.get("name", "")).strip()
        account_number = str(body.get("account_number", "")).strip()
        bank_code = str(body.get("bank_code", "")).strip()

        if not name or not account_number or not bank_code:
            raise ValueError(
                "name, account_number and bank_code are required."
            )

        result = create_transfer_recipient(
            name=name,
            account_number=account_number,
            bank_code=bank_code,
            currency=str(
                body.get("currency", "NGN")
            ).upper().strip(),
            email=getattr(request.user, "email", ""),
        )

        return JsonResponse({
            "ok": True,
            "recipient": result,
        })

    except Exception as exc:
        return JsonResponse(
            {"ok": False, "error": str(exc)},
            status=400,
        )


@login_required
@require_POST
def create_paystack_withdrawal(request):
    try:
        body = json.loads(request.body.decode("utf-8"))

        recipient_code = str(
            body.get("recipient_code", "")
        ).strip()

        if not recipient_code:
            raise ValueError(
                "Paystack recipient is required."
            )

        withdrawal, _ = create_withdrawal(
            user=request.user,
            amount=body.get("amount"),
            currency=str(
                body.get("currency", "NGN")
            ).upper().strip(),
            method="bank",
            destination_reference=recipient_code,
            provider=WithdrawalRequest.PROVIDER_PAYSTACK,
            provider_recipient=recipient_code,
        )

        data = initiate_transfer(
            withdrawal=withdrawal,
            recipient_code=recipient_code,
        )

        withdrawal.refresh_from_db()

        return JsonResponse({
            "ok": True,
            "withdrawal_id": withdrawal.pk,
            "status": withdrawal.status,
            "provider_reference": withdrawal.provider_reference,
            "provider_status": data.get("status"),
        })

    except Exception as exc:
        return JsonResponse(
            {"ok": False, "error": str(exc)},
            status=400,
        )


@csrf_exempt
@require_POST
def paystack_transfer_webhook(request):
    signature = request.headers.get(
        "X-Paystack-Signature",
        "",
    )

    if not verify_signature(request.body, signature):
        return JsonResponse(
            {"ok": False, "error": "Invalid signature."},
            status=401,
        )

    try:
        payload = json.loads(
            request.body.decode("utf-8")
        )

        handled = handle_transfer_webhook(payload)

        return JsonResponse({
            "ok": True,
            "handled": handled,
        })

    except Exception as exc:
        return JsonResponse(
            {"ok": False, "error": str(exc)},
            status=400,
        )


def _provider_webhook_response(request, provider_name):
    from .provider_base import PayoutProviderError
    from .router import get_provider

    provider = get_provider(provider_name)

    headers = {
        key: value
        for key, value in request.headers.items()
    }

    if provider_name == "stripe_connect":
        signature = request.headers.get("Stripe-Signature", "")
    elif provider_name == "airwallex":
        signature = (
            request.headers.get("x-signature")
            or request.headers.get("X-Signature")
            or ""
        )
    elif provider_name == "nowpayments":
        signature = (
            request.headers.get("x-nowpayments-sig")
            or request.headers.get("X-Nowpayments-Sig")
            or ""
        )
    else:
        signature = ""

    try:
        provider.verify_webhook(
            raw_body=request.body,
            signature=signature,
            headers=headers,
        )
    except PayoutProviderError as exc:
        return JsonResponse(
            {"ok": False, "error": str(exc)},
            status=401,
        )
    except Exception:
        return JsonResponse(
            {"ok": False, "error": "Webhook authentication failed."},
            status=401,
        )

    try:
        payload = json.loads(
            request.body.decode("utf-8")
        )
    except (UnicodeDecodeError, json.JSONDecodeError):
        return JsonResponse(
            {"ok": False, "error": "Invalid JSON payload."},
            status=400,
        )

    try:
        handled = provider.handle_webhook(
            payload=payload,
        )
    except Exception:
        return JsonResponse(
            {"ok": False, "error": "Webhook processing failed."},
            status=400,
        )

    return JsonResponse({
        "ok": True,
        "handled": bool(handled),
    })


@csrf_exempt
@require_POST
def stripe_connect_webhook(request):
    return _provider_webhook_response(
        request,
        "stripe_connect",
    )


@csrf_exempt
@require_POST
def airwallex_webhook(request):
    return _provider_webhook_response(
        request,
        "airwallex",
    )


@csrf_exempt
@require_POST
def mangopay_webhook(request):
    return _provider_webhook_response(
        request,
        "mangopay",
    )


@csrf_exempt
@require_POST
def nowpayments_webhook(request):
    return _provider_webhook_response(
        request,
        "nowpayments",
    )
