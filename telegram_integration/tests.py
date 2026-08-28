from urllib.parse import parse_qsl
import hashlib
import hmac
import json
import time
from urllib.parse import urlencode

from django.contrib.auth.models import User
from django.test import TestCase, override_settings

from accounts.models import Profile
from .models import TelegramAccount
from .shopu_auth import authenticate_init_data


class TelegramAuthenticationSecurityTests(TestCase):

    BOT_TOKEN = "123456:TEST_BOT_TOKEN"

    def make_init_data(self, telegram_id=987654321, username="testtg",
                       auth_date=None, extra=None):
        if auth_date is None:
            auth_date = int(time.time())

        user = {
            "id": telegram_id,
            "first_name": "Test",
            "username": username,
        }

        data = {
            "auth_date": str(auth_date),
            "query_id": "AAE_TEST_QUERY",
            "user": json.dumps(user, separators=(",", ":")),
        }

        if extra:
            data.update(extra)

        check = "\n".join(
            f"{k}={v}" for k, v in sorted(data.items())
        )

        secret = hmac.new(
            b"WebAppData",
            self.BOT_TOKEN.encode(),
            hashlib.sha256,
        ).digest()

        data["hash"] = hmac.new(
            secret,
            check.encode(),
            hashlib.sha256,
        ).hexdigest()

        return urlencode(data)

    @override_settings(
        TELEGRAM_BOT_TOKEN=BOT_TOKEN,
        TELEGRAM_INIT_DATA_MAX_AGE_SECONDS=3600,
        TELEGRAM_INIT_DATA_MAX_FUTURE_SECONDS=300,
    )
    def test_valid_init_data_authenticates(self):
        init_data = self.make_init_data()

        user = authenticate_init_data(init_data)

        self.assertIsNotNone(user)
        self.assertEqual(
            user.telegram_account.telegram_user_id,
            987654321,
        )
        self.assertEqual(user.profile.telegram_id, "987654321")

    @override_settings(
        TELEGRAM_BOT_TOKEN=BOT_TOKEN,
        TELEGRAM_INIT_DATA_MAX_AGE_SECONDS=3600,
    )
    def test_invalid_hash_rejected(self):
        init_data = self.make_init_data()
        init_data = init_data.replace("hash=", "hash=BAD")

        self.assertIsNone(authenticate_init_data(init_data))

    @override_settings(
        TELEGRAM_BOT_TOKEN=BOT_TOKEN,
        TELEGRAM_INIT_DATA_MAX_AGE_SECONDS=3600,
    )
    def test_expired_init_data_rejected(self):
        init_data = self.make_init_data(
            auth_date=int(time.time()) - 7200
        )

        self.assertIsNone(authenticate_init_data(init_data))

    @override_settings(
        TELEGRAM_BOT_TOKEN=BOT_TOKEN,
        TELEGRAM_INIT_DATA_MAX_AGE_SECONDS=3600,
        TELEGRAM_INIT_DATA_MAX_FUTURE_SECONDS=300,
    )
    def test_far_future_init_data_rejected(self):
        init_data = self.make_init_data(
            auth_date=int(time.time()) + 3600
        )

        self.assertIsNone(authenticate_init_data(init_data))

    @override_settings(
        TELEGRAM_BOT_TOKEN=BOT_TOKEN,
        TELEGRAM_INIT_DATA_MAX_AGE_SECONDS=3600,
    )
    def test_missing_hash_rejected(self):
        init_data = self.make_init_data()
        init_data = init_data.split("&hash=", 1)[0]

        self.assertIsNone(authenticate_init_data(init_data))

    @override_settings(
        TELEGRAM_BOT_TOKEN=BOT_TOKEN,
        TELEGRAM_INIT_DATA_MAX_AGE_SECONDS=3600,
    )
    def test_username_collision_does_not_take_over_existing_user(self):
        existing = User.objects.create_user(
            username="sameusername",
            password="test",
        )
        Profile.objects.create(
            user=existing,
            role=Profile.BUYER,
        )

        init_data = self.make_init_data(
            telegram_id=555111222,
            username="sameusername",
        )

        authenticated = authenticate_init_data(init_data)

        self.assertIsNotNone(authenticated)
        self.assertNotEqual(authenticated.id, existing.id)
        self.assertEqual(
            authenticated.telegram_account.telegram_user_id,
            555111222,
        )
        self.assertFalse(
            TelegramAccount.objects.filter(
                telegram_user_id=555111222,
                user=existing,
            ).exists()
        )

    @override_settings(
        TELEGRAM_BOT_TOKEN=BOT_TOKEN,
        TELEGRAM_INIT_DATA_MAX_AGE_SECONDS=3600,
    )
    def test_existing_telegram_id_returns_same_user(self):
        first = authenticate_init_data(
            self.make_init_data(
                telegram_id=444333222,
                username="first_name",
            )
        )

        second = authenticate_init_data(
            self.make_init_data(
                telegram_id=444333222,
                username="changed_username",
            )
        )

        self.assertEqual(first.id, second.id)
        self.assertEqual(
            TelegramAccount.objects.filter(
                telegram_user_id=444333222
            ).count(),
            1,
        )

    @override_settings(
        TELEGRAM_BOT_TOKEN=BOT_TOKEN,
        TELEGRAM_INIT_DATA_MAX_AGE_SECONDS=3600,
    )
    def test_missing_telegram_id_rejected(self):
        init_data = self.make_init_data()
        data = dict(parse_qsl(init_data, keep_blank_values=True))

        user_data = json.loads(data["user"])
        user_data.pop("id")
        data["user"] = json.dumps(user_data, separators=(",", ":"))

        check = "\n".join(
            f"{k}={v}" for k, v in sorted(
                (k, v) for k, v in data.items() if k != "hash"
            )
        )

        secret = hmac.new(
            b"WebAppData",
            self.BOT_TOKEN.encode(),
            hashlib.sha256,
        ).digest()

        data["hash"] = hmac.new(
            secret,
            check.encode(),
            hashlib.sha256,
        ).hexdigest()

        self.assertIsNone(
            authenticate_init_data(urlencode(data))
        )
