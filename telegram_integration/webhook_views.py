import json

from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt

from telegram import Update
from telegram.ext import Application, CommandHandler

from .telegram_bot import (
    start,
    accept_terms_command,
    referral_command,
    help_command,
)


_application = None


def get_application():
    global _application

    if _application is not None:
        return _application

    token = getattr(settings, "TELEGRAM_MAIN_BOT_TOKEN", "").strip()

    if not token:
        raise RuntimeError(
            "TELEGRAM_MAIN_BOT_TOKEN is not configured."
        )

    _application = (
        Application.builder()
        .token(token)
        .updater(None)
        .build()
    )

    _application.add_handler(CommandHandler("start", start))
    _application.add_handler(
        CommandHandler("acceptterms", accept_terms_command)
    )
    _application.add_handler(
        CommandHandler("referral", referral_command)
    )
    _application.add_handler(
        CommandHandler("help", help_command)
    )

    return _application


@csrf_exempt
async def telegram_webhook(request):
    if request.method != "POST":
        return JsonResponse(
            {"ok": False, "error": "POST required"},
            status=405,
        )

    secret = getattr(
        settings,
        "TELEGRAM_WEBHOOK_SECRET",
        "",
    ).strip()

    if secret:
        received_secret = request.headers.get(
            "X-Telegram-Bot-Api-Secret-Token",
            "",
        )

        if received_secret != secret:
            return JsonResponse(
                {"ok": False, "error": "Unauthorized"},
                status=401,
            )

    try:
        data = json.loads(request.body.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return JsonResponse(
            {"ok": False, "error": "Invalid JSON"},
            status=400,
        )

    try:
        application = get_application()

        await application.initialize()

        update = Update.de_json(
            data,
            application.bot,
        )

        await application.process_update(update)

        return HttpResponse("OK")

    except Exception as exc:
        print(f"Telegram webhook error: {exc}")

        return JsonResponse(
            {
                "ok": False,
                "error": "Webhook processing failed",
            },
            status=500,
        )
