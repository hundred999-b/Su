import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    WebAppInfo,
)
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
)

from django.conf import settings

from referrals.models import ReferralProgramSettings
from .bot import (
    get_or_create_telegram_user,
    apply_start_referral,
    get_referral_link,
)


MINIAPP_URL = getattr(settings, "MINIAPP_URL", "").strip()


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tg_user = update.effective_user

    user = get_or_create_telegram_user(
        tg_user.id,
        tg_user.username,
    )

    start_argument = context.args[0] if context.args else ""
    apply_start_referral(user, start_argument)

    name = tg_user.first_name or tg_user.username or "there"

    text = (
        f"Welcome to ShopU, {name}! 👋\n\n"
        "Buy, sell and use secure escrow for transactions."
    )

    rows = []

    if MINIAPP_URL:
        rows.append([
            InlineKeyboardButton(
                "🛍 Open ShopU",
                web_app=WebAppInfo(url=MINIAPP_URL),
            )
        ])

        rows.append([
            InlineKeyboardButton(
                "🔐 Use Escrow",
                web_app=WebAppInfo(
                    url=MINIAPP_URL + "#escrow"
                ),
            )
        ])

        rows.append([
            InlineKeyboardButton(
                "🌐 Open in Browser",
                url=MINIAPP_URL,
            )
        ])

    await update.message.reply_text(
        text,
        reply_markup=InlineKeyboardMarkup(rows),
    )


async def accept_terms_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    from stage4.models import TermsDocument
    from stage4.services import accept_terms, active_terms

    user = get_or_create_telegram_user(
        update.effective_user.id,
        update.effective_user.username,
    )

    terms = active_terms(TermsDocument.BUYER)

    if not terms:
        await update.message.reply_text(
            "Buyer Terms are not configured yet."
        )
        return

    if (
        not context.args
        or context.args[0].lower()
        not in ("yes", "agree", "accept")
    ):
        await update.message.reply_text(
            f"{terms.title} v{terms.version}\n\n"
            f"{terms.body}\n\n"
            "If you have read and agree to these terms, send:\n"
            "/acceptterms yes"
        )
        return

    acceptance = accept_terms(
        user,
        terms,
        purpose="purchase",
    )

    await update.message.reply_text(
        f"✅ Buyer Terms {terms.version} accepted at "
        f"{acceptance.accepted_at.isoformat()}."
    )


async def referral_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    tg_user = update.effective_user

    user = get_or_create_telegram_user(
        tg_user.id,
        tg_user.username,
    )

    bot_username = getattr(
        settings,
        "TELEGRAM_BOT_USERNAME",
        "",
    ).strip().lstrip("@")

    if not bot_username:
        await update.message.reply_text(
            "Referral links are not configured yet."
        )
        return

    link = get_referral_link(
        user,
        bot_username,
    )

    program = ReferralProgramSettings.get_solo()

    status = (
        "enabled"
        if program.enabled
        else "disabled"
    )

    await update.message.reply_text(
        f"🎁 Your ShopU referral link:\n\n"
        f"{link}\n\n"
        f"Program: {status}\n"
        f"Commission: {program.commission_percent}%\n"
        f"Eligible completed transactions per "
        f"referred user: first "
        f"{program.transactions_limit}"
    )


async def help_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    await update.message.reply_text(
        "/start - Open ShopU\n"
        "/acceptterms - View current Buyer Terms; "
        "add 'yes' to accept\n"
        "/referral - Get your referral link\n"
        "/help - Show help"
    )


def build_bot_application():
    token = getattr(
        settings,
        "TELEGRAM_MAIN_BOT_TOKEN",
        "",
    ).strip()

    if not token:
        raise RuntimeError(
            "TELEGRAM_MAIN_BOT_TOKEN is not configured"
        )

    if not MINIAPP_URL:
        raise RuntimeError(
            "MINIAPP_URL is not configured. "
            "Set it to the HTTPS URL of your Mini App."
        )

    application = (
        Application.builder()
        .token(token)
        .updater(None)
        .build()
    )

    application.add_handler(
        CommandHandler("start", start)
    )

    application.add_handler(
        CommandHandler(
            "acceptterms",
            accept_terms_command,
        )
    )

    application.add_handler(
        CommandHandler(
            "referral",
            referral_command,
        )
    )

    application.add_handler(
        CommandHandler("help", help_command)
    )

    return application
