import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from .nowpayments import create_payment, process_ipn, verify_ipn_signature


def _user(request):
    from telegram_integration.shopu_auth import authenticate_init_data
    return authenticate_init_data(request.POST.get("init_data") or request.GET.get("init_data"))


@csrf_exempt
def initialize_crypto_payment(request):
    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=405)
    user = _user(request)
    if not user:
        return JsonResponse({"error": "Telegram authentication required"}, status=401)
    try:
        deposit = create_payment(
            user=user,
            amount=request.POST.get("amount"),
            price_currency=request.POST.get("currency"),
            pay_currency=request.POST.get("pay_currency"),
            order_id=request.POST.get("order_id"),
        )
    except Exception as exc:
        return JsonResponse({"error": str(exc)}, status=400)
    return JsonResponse({
        "success": True,
        "deposit_id": deposit.id,
        "payment_id": deposit.provider_payment_id,
        "pay_currency": deposit.pay_currency,
        "pay_amount": str(deposit.pay_amount or ""),
        "address": deposit.address,
        "payment_url": deposit.payment_url,
        "status": deposit.status,
    })


@csrf_exempt
def nowpayments_ipn(request):
    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=405)
    try:
        payload = json.loads(request.body.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return JsonResponse({"error": "Invalid JSON"}, status=400)
    if not verify_ipn_signature(payload, request.headers.get("x-nowpayments-sig", "")):
        return JsonResponse({"error": "Invalid signature"}, status=401)
    try:
        deposit = process_ipn(payload)
    except Exception as exc:
        return JsonResponse({"received": True, "processed": False, "error": str(exc)}, status=500)
    return JsonResponse({"received": True, "processed": True, "deposit_id": deposit.id})
