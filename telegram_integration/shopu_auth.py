import hashlib
import hmac
import json
import time
from urllib.parse import parse_qsl

from django.conf import settings
from django.contrib.auth.models import User
from django.utils import timezone

from accounts.models import Profile
from referrals.services import ensure_referral_profile


def authenticate_init_data(init_data):
    init_data = (init_data or "").strip()
    token = getattr(settings, "TELEGRAM_BOT_TOKEN", "")
    if not init_data or not token:
        return None

    try:
        parsed = dict(parse_qsl(init_data, keep_blank_values=True))
        received = parsed.pop("hash", None)
        if not received:
            return None

        check = "\n".join(f"{k}={v}" for k, v in sorted(parsed.items()))
        secret = hmac.new(
            b"WebAppData", token.encode(), hashlib.sha256
        ).digest()
        expected = hmac.new(
            secret, check.encode(), hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(expected, received):
            return None

        auth_date = int(parsed.get("auth_date", "0"))
        now = time.time()
        max_age = int(
            getattr(settings, "TELEGRAM_INIT_DATA_MAX_AGE_SECONDS", 3600)
        )
        max_future = int(
            getattr(settings, "TELEGRAM_INIT_DATA_MAX_FUTURE_SECONDS", 300)
        )

        # Reject missing, expired, or implausibly future-dated init data.
        if not auth_date:
            return None
        if now - auth_date > max_age:
            return None
        if auth_date - now > max_future:
            return None

        raw = parsed.get("user")
        tg = json.loads(raw) if raw else {}
        tid = str(tg.get("id", "")).strip()
        if not tid:
            return None

        telegram_id = int(tid)
        username = (tg.get("username") or "").strip()

        from .models import TelegramAccount

        # IMPORTANT:
        # Telegram numeric ID is the authoritative identity.
        # Never attach a new Telegram identity to an existing Django
        # account merely because the usernames happen to match.
        account = (
            TelegramAccount.objects.filter(telegram_user_id=telegram_id)
            .select_related("user")
            .first()
        )

        if account:
            user = account.user
        else:
            # Recover a previously linked profile if the TelegramAccount
            # record is missing but the Profile still contains the ID.
            profile = (
                Profile.objects.filter(telegram_id=tid)
                .select_related("user")
                .first()
            )

            if profile:
                user = profile.user
            else:
                # Create a fresh Django user. Username collisions are
                # handled without linking identities.
                base = username or f"tg_{tid}"
                candidate = base
                n = 1
                while User.objects.filter(username=candidate).exists():
                    candidate = f"{base}_{n}"
                    n += 1

                user = User.objects.create_user(username=candidate)
                Profile.objects.create(
                    user=user,
                    role=Profile.BUYER,
                    telegram_id=tid,
                )

            account = TelegramAccount.objects.update_or_create(
                telegram_user_id=telegram_id,
                defaults={
                    "user": user,
                    "username": username,
                    "verified": True,
                    "verified_at": timezone.now(),
                },
            )[0]

        profile, _ = Profile.objects.get_or_create(user=user)
        profile.telegram_id = tid
        profile.last_seen_at = timezone.now()
        profile.save(update_fields=["telegram_id", "last_seen_at"])
        ensure_referral_profile(user)
        return user
    except (ValueError, TypeError, json.JSONDecodeError, KeyError):
        return None
