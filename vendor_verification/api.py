from django.contrib.auth import get_user_model
from django.http import JsonResponse
from django.views.decorators.http import require_GET, require_POST

from .models import VendorVerification, VerificationProgramSettings
from .services import apply_for_verification
from .trust import vendor_badges

User = get_user_model()


@require_GET
def vendor_profile(request, seller_id):
    seller = User.objects.filter(pk=seller_id).first()
    if not seller:
        return JsonResponse({"error": "Seller not found"}, status=404)

    verification = VendorVerification.objects.filter(seller=seller).first()
    from marketplace.models import Order
    from stage4.models import DisputeEvent
    completed = Order.objects.filter(product__seller=seller, status=Order.COMPLETED).count()
    disputes = DisputeEvent.objects.filter(order__product__seller=seller, event_type="opened").count()
    reviews = __import__("reviews.models", fromlist=["Review"]).Review.objects.filter(seller=seller, visible=True)
    from django.db.models import Avg
    avg = reviews.aggregate(value=Avg("rating"))["value"]
    return JsonResponse({
        "seller": {"id": seller.id, "username": seller.username},
        "stats": {"completed_transactions": completed, "dispute_count": disputes, "dispute_rate_percent": round((disputes / completed) * 100, 2) if completed else 0, "review_count": reviews.count(), "average_rating": round(float(avg), 2) if avg else None},
        "trust": vendor_badges(seller),
        "verification": {
            "status": verification.status if verification else "unverified",
            "badge": verification.badge if verification else "",
            "badge_level": verification.badge_level if verification else "unverified",
            "identity_verified": verification.identity_verified if verification else False,
            "business_verified": verification.business_verified if verification else False,
            "payment_history_verified": verification.payment_history_verified if verification else False,
            "transaction_history_verified": verification.transaction_history_verified if verification else False,
        },
    })


@require_GET
def verification_settings(request):
    program = VerificationProgramSettings.get_solo()
    return JsonResponse({
        "enabled": program.enabled,
        "requirements": program.requirements(),
    })


@require_POST
def apply(request):
    from telegram_integration.shopu_auth import authenticate_init_data

    seller = authenticate_init_data(
        request.POST.get("init_data") or request.GET.get("init_data")
    )
    if not seller:
        return JsonResponse({"error": "Telegram authentication required"}, status=401)
    try:
        verification = apply_for_verification(seller)
    except ValueError as e:
        return JsonResponse({"error": str(e)}, status=400)
    return JsonResponse({
        "success": True,
        "status": verification.status,
    })
