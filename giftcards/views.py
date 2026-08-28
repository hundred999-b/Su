import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from .services import create_gift_card_purchase


def _user(request):
    from telegram_integration.shopu_auth import authenticate_init_data
    return authenticate_init_data(request.POST.get("init_data") or request.GET.get("init_data"))


@csrf_exempt
def buy_gift_card(request):
    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=405)
    user = _user(request)
    if not user:
        return JsonResponse({"error": "Telegram authentication required"}, status=401)
    try:
        purchase = create_gift_card_purchase(
            buyer=user,
            amount=request.POST.get("amount"),
            currency=request.POST.get("currency"),
            recipient_email=request.POST.get("recipient_email", "").strip(),
            provider=request.POST.get("provider") or None,
        )
    except Exception as exc:
        return JsonResponse({"error": str(exc)}, status=400)
    return JsonResponse({
        "success": True,
        "purchase_id": purchase.id,
        "payment_id": purchase.payment_id,
        "provider": purchase.payment.provider,
        "checkout_url": purchase.payment.authorization_url,
        "status": purchase.status,
    })

@csrf_exempt
def submit_gift_card_topup_api(request):
    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=405)
    user = _user(request)
    if not user:
        return JsonResponse({"error": "Telegram authentication required"}, status=401)
    try:
        from .services import submit_gift_card_topup
        topup = submit_gift_card_topup(
            user=user,
            brand=request.POST.get("brand"),
            code=request.POST.get("code"),
            claimed_amount=request.POST.get("amount"),
            claimed_currency=request.POST.get("currency"),
            country=request.POST.get("country", ""),
            user_note=request.POST.get("note", ""),
            purchase_proof=request.POST.get("purchase_proof", ""),
        )
    except Exception as exc:
        return JsonResponse({"error": str(exc)}, status=400)
    return JsonResponse({
        "success": True,
        "topup_id": topup.id,
        "status": topup.status,
        "message": "Gift card submitted for verification. Your wallet will be credited after confirmation.",
    })
