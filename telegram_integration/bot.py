import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from django.contrib.auth.models import User
from marketplace.models import Product, Order
from ledger.transaction_service import wallet_balance
from referrals.services import ensure_referral_profile, attribute_referral, referral_link
from referrals.models import ReferralProgramSettings


def get_or_create_telegram_user(telegram_user_id, username=None):
    from .models import TelegramAccount

    account = (
        TelegramAccount.objects.filter(telegram_user_id=telegram_user_id)
        .select_related("user")
        .first()
    )
    if account:
        if username and account.username != username:
            account.username = username
            account.save(update_fields=["username"])
        ensure_referral_profile(account.user)
        return account.user

    base = username or f"telegram_{telegram_user_id}"
    clean = "".join(c for c in base if c.isalnum() or c in "_-")[:120]
    if not clean:
        clean = f"telegram_{telegram_user_id}"

    candidate = clean
    counter = 1
    while User.objects.filter(username=candidate).exists():
        candidate = f"{clean}_{counter}"
        counter += 1

    user = User.objects.create_user(username=candidate)
    TelegramAccount.objects.create(
        user=user,
        telegram_user_id=telegram_user_id,
        username=username or "",
        verified=False,
    )

    from ledger.wallet_service import ensure_wallet
    ensure_wallet(user, "USD")
    ensure_referral_profile(user)
    return user


def products():
    return list(Product.objects.filter(active=True).select_related("seller"))


def product_details(product_id):
    return Product.objects.filter(
        pk=product_id, active=True
    ).select_related("seller").first()


def user_orders(user):
    return list(
        Order.objects.filter(buyer=user)
        .select_related("product")
        .order_by("-created_at")
    )


def user_wallet(user):
    return wallet_balance(user, "USD")


def get_referral_link(user, bot_username):
    return referral_link(bot_username, user)


def apply_start_referral(user, start_argument):
    value = (start_argument or "").strip()
    if value.startswith("ref_"):
        return attribute_referral(user, value[4:])
    return ensure_referral_profile(user)
