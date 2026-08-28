import json
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.urls import resolve

from .provider_base import PayoutProviderError


class FakeProvider:
    def __init__(self, name):
        self.name = name
        self.verified = False
        self.handled = False

    def verify_webhook(self, *, raw_body, signature="", headers=None):
        self.verified = True

        if self.name == "mangopay":
            if (headers or {}).get("X-Shopu-Test-Trusted") != "1":
                raise PayoutProviderError("Webhook not trusted.")

        elif not signature:
            raise PayoutProviderError("Webhook signature missing.")

        return True

    def handle_webhook(self, *, payload):
        self.handled = True
        return True


@override_settings(SECURE_SSL_REDIRECT=False)
class WithdrawalWebhookEndpointTests(TestCase):

    def setUp(self):
        self.payload = json.dumps({
            "shopu_withdrawal_id": "123",
            "status": "finished",
        }).encode()

    def test_routes_exist(self):
        routes = {
            "stripe_connect": "stripe_connect/webhook/",
            "airwallex": "airwallex/webhook/",
            "mangopay": "mangopay/webhook/",
            "nowpayments": "nowpayments/webhook/",
        }

        for provider, path in routes.items():
            match = resolve("/api/withdrawals/" + path)
            self.assertIsNotNone(match)
            self.assertEqual(
                match.func.__name__,
                {
                    "stripe_connect": "stripe_connect_webhook",
                    "airwallex": "airwallex_webhook",
                    "mangopay": "mangopay_webhook",
                    "nowpayments": "nowpayments_webhook",
                }[provider],
            )

    @patch("withdrawals.router.get_provider")
    def test_stripe_webhook_dispatches_after_verification(self, get_provider):
        provider = FakeProvider("stripe_connect")
        get_provider.return_value = provider

        response = self.client.post(
            "/api/withdrawals/stripe_connect/webhook/",
            data=self.payload,
            content_type="application/json",
            HTTP_STRIPE_SIGNATURE="test-signature",
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(provider.verified)
        self.assertTrue(provider.handled)

    @patch("withdrawals.router.get_provider")
    def test_airwallex_webhook_dispatches_after_verification(
        self,
        get_provider,
    ):
        provider = FakeProvider("airwallex")
        get_provider.return_value = provider

        response = self.client.post(
            "/api/withdrawals/airwallex/webhook/",
            data=self.payload,
            content_type="application/json",
            HTTP_X_SIGNATURE="test-signature",
            HTTP_X_TIMESTAMP="1234567890000",
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(provider.verified)
        self.assertTrue(provider.handled)

    @patch("withdrawals.router.get_provider")
    def test_nowpayments_webhook_dispatches_after_verification(
        self,
        get_provider,
    ):
        provider = FakeProvider("nowpayments")
        get_provider.return_value = provider

        response = self.client.post(
            "/api/withdrawals/nowpayments/webhook/",
            data=self.payload,
            content_type="application/json",
            HTTP_X_NOWPAYMENTS_SIG="test-signature",
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(provider.verified)
        self.assertTrue(provider.handled)

    @patch("withdrawals.router.get_provider")
    def test_mangopay_requires_trusted_boundary(self, get_provider):
        provider = FakeProvider("mangopay")
        get_provider.return_value = provider

        response = self.client.post(
            "/api/withdrawals/mangopay/webhook/",
            data=self.payload,
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 401)
        self.assertTrue(provider.verified)
        self.assertFalse(provider.handled)

    @patch("withdrawals.router.get_provider")
    def test_missing_signature_rejected_for_stripe(self, get_provider):
        provider = FakeProvider("stripe_connect")
        get_provider.return_value = provider

        response = self.client.post(
            "/api/withdrawals/stripe_connect/webhook/",
            data=self.payload,
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 401)
        self.assertTrue(provider.verified)
        self.assertFalse(provider.handled)

    @patch("withdrawals.router.get_provider")
    def test_missing_signature_rejected_for_airwallex(self, get_provider):
        provider = FakeProvider("airwallex")
        get_provider.return_value = provider

        response = self.client.post(
            "/api/withdrawals/airwallex/webhook/",
            data=self.payload,
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 401)
        self.assertTrue(provider.verified)
        self.assertFalse(provider.handled)

    @patch("withdrawals.router.get_provider")
    def test_missing_signature_rejected_for_nowpayments(
        self,
        get_provider,
    ):
        provider = FakeProvider("nowpayments")
        get_provider.return_value = provider

        response = self.client.post(
            "/api/withdrawals/nowpayments/webhook/",
            data=self.payload,
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 401)
        self.assertTrue(provider.verified)
        self.assertFalse(provider.handled)

    @patch("withdrawals.router.get_provider")
    def test_invalid_json_is_rejected_after_authentication(
        self,
        get_provider,
    ):
        provider = FakeProvider("stripe_connect")
        get_provider.return_value = provider

        response = self.client.post(
            "/api/withdrawals/stripe_connect/webhook/",
            data=b"not-json",
            content_type="application/json",
            HTTP_STRIPE_SIGNATURE="test-signature",
        )

        self.assertEqual(response.status_code, 400)
        self.assertTrue(provider.verified)
        self.assertFalse(provider.handled)
