import json

from django.conf import settings
from django.http import (
    HttpResponse,
    JsonResponse,
)
from django.views.decorators.csrf import csrf_exempt

from telegram import Update

from .telegram_bot import build_bot_application


@csrf_exempt
async def telegram_webhook(request):
    if request.method != "POST":
        return JsonResponse(
            {
                "ok": False,
                "error": "POST required",
            },
            status=405,
        )

    expected_secret = getattr(
        settings,
        "TELEGRAM_WEBHOOK_SECRET",
        "",
    ).strip()

    received_secret = request.headers.get(
        "X-Telegram-Bot-Api-Secret-Token",
        "",
    )

    if (
        expected_secret
        and received_secret != expected_secret
    ):
        return JsonResponse(
            {
                "ok": False,
                "error": "invalid secret",
            },
            status=403,
        )

    try:
        payload = json.loads(
            request.body.decode("utf-8")
        )
    except (ValueError, UnicodeDecodeError):
        return JsonResponse(
            {
                "ok": False,
                "error": "invalid JSON",
            },
            status=400,
        )

    try:
        application = build_bot_application()

        await application.initialize()

        update = Update.de_json(
            payload,
            application.bot,
        )

        await application.process_update(update)

        await application.shutdown()

        return JsonResponse(
            {"ok": True},
            status=200,
        )

    except Exception as exc:
        print(
            "Telegram webhook error:",
            repr(exc),
        )

        return JsonResponse(
            {
                "ok": False,
                "error": "telegram processing failed",
            },
            status=500,
        )
