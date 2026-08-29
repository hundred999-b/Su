import os

from django.conf import settings
from django.core.management.base import BaseCommand
from telegram import Bot


class Command(BaseCommand):
    help = "Register the ShopU Telegram bot webhook."

    def handle(self, *args, **options):
        token = getattr(settings, "TELEGRAM_MAIN_BOT_TOKEN", "").strip()
        if not token:
            raise RuntimeError(
                "TELEGRAM_MAIN_BOT_TOKEN is not configured."
            )

        host = os.environ.get("RENDER_EXTERNAL_URL", "").strip().rstrip("/")
        if not host:
            host = "https://shopu.onrender.com"

        webhook_url = f"{host}/telegram/webhook/"

        secret = getattr(settings, "TELEGRAM_WEBHOOK_SECRET", "").strip()

        bot = Bot(token=token)

        result = bot.set_webhook(
            url=webhook_url,
            secret_token=secret if secret else None,
            allowed_updates=["message"],
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"Telegram webhook registered: {webhook_url}"
            )
        )
        self.stdout.write(f"Telegram API response: {result}")
