import json

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

from .services import (
    initialize_paystack_payment,
    verify_paystack_payment,
    verify_paystack_signature,
)


def _user(request):
    from telegram_integration.shopu_auth import authenticate_init_data
    return authenticate_init_data(
        request.POST.get("init_data") or request.GET.get("init_data")
    )


@csrf_exempt
def initialize_paystack(request):
    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=405)
    user = _user(request)
    if not user:
        return JsonResponse({"error": "Telegram authentication required"}, status=401)

    try:
        payment = initialize_paystack_payment(
            user=user,
            amount=request.POST.get("amount"),
            currency=request.POST.get("currency"),
            email=request.POST.get("email"),
        )
    except Exception as exc:
        return JsonResponse({"error": str(exc)}, status=400)

    return JsonResponse({
        "success": True,
        "payment_id": payment.id,
        "reference": payment.provider_reference,
        "authorization_url": payment.authorization_url,
        "access_code": payment.access_code,
        "status": payment.status,
    })


@csrf_exempt
def verify_payment(request):
    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=405)
    user = _user(request)
    if not user:
        return JsonResponse({"error": "Telegram authentication required"}, status=401)

    reference = (request.POST.get("reference") or "").strip()
    if not reference:
        return JsonResponse({"error": "reference is required"}, status=400)

    from .models import Payment
    if not Payment.objects.filter(
        provider="paystack", provider_reference=reference, user=user
    ).exists():
        return JsonResponse({"error": "Payment not found"}, status=404)

    try:
        payment, provider_data = verify_paystack_payment(reference)
    except Exception as exc:
        return JsonResponse({"error": str(exc)}, status=400)

    return JsonResponse({
        "success": True,
        "status": payment.status,
        "reference": payment.provider_reference,
        "provider_status": provider_data.get("status"),
    })


@csrf_exempt
def paystack_webhook(request):
    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=405)

    signature = request.headers.get("x-paystack-signature", "")
    if not verify_paystack_signature(request.body, signature):
        return JsonResponse({"error": "Invalid signature"}, status=401)

    try:
        event = json.loads(request.body.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    if event.get("event") == "charge.success":
        data = event.get("data") or {}
        reference = data.get("reference")
        if reference:
            from .models import Payment
            payment = Payment.objects.filter(
                provider="paystack", provider_reference=reference
            ).first()
            if payment:
                try:
                    verify_paystack_payment(reference)
                except Exception as exc:
                    return JsonResponse(
                        {"received": True, "processed": False, "error": str(exc)},
                        status=500,
                    )
    return JsonResponse({"received": True})

@csrf_exempt
def initialize_stripe(request):
    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=405)
    user = _user(request)
    if not user:
        return JsonResponse({"error": "Telegram authentication required"}, status=401)
    try:
        from .stripe_service import initialize_stripe_payment
        payment = initialize_stripe_payment(
            user=user,
            amount=request.POST.get("amount"),
            currency=request.POST.get("currency"),
            email=request.POST.get("email"),
        )
    except Exception as exc:
        return JsonResponse({"error": str(exc)}, status=400)
    return JsonResponse({
        "success": True,
        "payment_id": payment.id,
        "reference": payment.provider_reference,
        "checkout_url": payment.authorization_url,
        "status": payment.status,
    })


@csrf_exempt
def stripe_webhook(request):
    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=405)
    signature = request.headers.get("Stripe-Signature", "")
    try:
        from .stripe_service import handle_stripe_webhook
        handle_stripe_webhook(request.body, signature)
    except Exception as exc:
        return JsonResponse({"received": False, "error": str(exc)}, status=400)
    return JsonResponse({"received": True})

@csrf_exempt
def initialize_generic_payment(request):
    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=405)
    user = _user(request)
    if not user:
        return JsonResponse({"error": "Telegram authentication required"}, status=401)
    try:
        from .services import initialize_payment
        payment = initialize_payment(
            user=user,
            amount=request.POST.get("amount"),
            currency=request.POST.get("currency"),
            email=request.POST.get("email"),
            provider=request.POST.get("provider"),
        )
    except Exception as exc:
        return JsonResponse({"error": str(exc)}, status=400)
    return JsonResponse({
        "success": True,
        "payment_id": payment.id,
        "provider": payment.provider,
        "reference": payment.provider_reference,
        "checkout_url": payment.authorization_url,
        "status": payment.status,
    })
