from django.contrib.auth.models import User
from django.http import JsonResponse

from ledger.transaction_service import (
    test_deposit,
    wallet_balance,
)


def wallet(request):

    if not request.user.is_authenticated:
        return JsonResponse(
            {"error": "authentication required"},
            status=401,
        )

    balance = wallet_balance(request.user)

    return JsonResponse({
        "user": request.user.username,
        "currency": "USD",
        "balance": str(balance),
    })


def test_deposit_api(request):

    if request.method != "POST":
        return JsonResponse(
            {"error": "POST required"},
            status=405,
        )

    if not request.user.is_authenticated:
        return JsonResponse(
            {"error": "authentication required"},
            status=401,
        )

    tx = test_deposit(
        request.user,
        "100.00",
        "USD",
    )

    return JsonResponse({
        "test": True,
        "transaction_id": tx.transaction_id,
        "balance": str(
            wallet_balance(request.user)
        ),
    })
