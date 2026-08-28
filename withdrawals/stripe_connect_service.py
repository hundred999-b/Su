import uuid

import requests
from django.conf import settings

from .provider_base import PayoutProvider, PayoutProviderError
from .services import (
    complete_withdrawal,
    fail_withdrawal,
    mark_withdrawal_processing,
)


class StripeConnectProvider(PayoutProvider):
    name = "stripe_connect"

    def _headers(self, account_id=None):
        key = getattr(settings, "STRIPE_SECRET_KEY", "").strip()

        if not key:
            raise PayoutProviderError(
                "STRIPE_SECRET_KEY is not configured."
            )

        headers = {
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/x-www-form-urlencoded",
        }

        if account_id:
            headers["Stripe-Account"] = account_id

        return headers

    def create_recipient(self, *, user, destination):
        account_id = str(
            destination.get("account_id", "")
        ).strip()

        if not account_id.startswith("acct_"):
            raise PayoutProviderError(
                "A valid Stripe connected account is required."
            )

        return {
            "account_id": account_id,
            "provider": self.name,
        }

    def initiate(self, *, withdrawal):
        account_id = withdrawal.provider_recipient

        if not account_id:
            raise PayoutProviderError(
                "Stripe Connect account is missing."
            )

        if not account_id.startswith("acct_"):
            raise PayoutProviderError(
                "Invalid Stripe connected account."
            )

        reference = (
            f"shopu_{withdrawal.pk}_{uuid.uuid4().hex[:20]}"
        )

        response = requests.post(
            "https://api.stripe.com/v1/payouts",
            headers=self._headers(account_id),
            data={
                "amount": int(withdrawal.amount * 100),
                "currency": withdrawal.currency.lower(),
                "metadata[shopu_withdrawal_id]": str(withdrawal.pk),
                "metadata[shopu_reference]": reference,
            },
            timeout=30,
        )

        if response.status_code >= 400:
            raise PayoutProviderError(
                response.text[:500]
            )

        data = response.json()

        payout_id = data.get("id")

        if not payout_id:
            raise PayoutProviderError(
                "Stripe returned no payout ID."
            )

        mark_withdrawal_processing(
            withdrawal.pk,
            provider_reference=payout_id,
            provider_recipient=account_id,
            metadata={
                "stripe_payout_id": payout_id,
                "stripe_status": data.get("status"),
                "stripe_account_id": account_id,
            },
        )

        return data

    def verify_webhook(self, *, raw_body, signature="", headers=None):
        try:
            import stripe
        except ImportError as exc:
            raise PayoutProviderError(
                "stripe package is not installed."
            ) from exc

        secret = getattr(
            settings,
            "STRIPE_WEBHOOK_SECRET",
            "",
        ).strip()

        if not secret:
            raise PayoutProviderError(
                "STRIPE_WEBHOOK_SECRET is not configured."
            )

        if not signature:
            raise PayoutProviderError(
                "Stripe webhook signature is missing."
            )

        try:
            return stripe.Webhook.construct_event(
                raw_body,
                signature,
                secret,
            )
        except Exception as exc:
            raise PayoutProviderError(
                "Invalid Stripe webhook signature."
            ) from exc

    def handle_webhook(self, *, payload):
        event_type = payload.get("type", "")
        data = (
            payload.get("data", {})
            .get("object", {})
        )

        metadata = data.get("metadata") or {}
        withdrawal_id = metadata.get(
            "shopu_withdrawal_id"
        )

        if not withdrawal_id:
            return False

        if event_type == "payout.paid":
            complete_withdrawal(
                int(withdrawal_id),
                provider_reference=data.get("id", ""),
                metadata={
                    "stripe_event": event_type,
                    "stripe_status": data.get("status"),
                },
            )
            return True

        if event_type == "payout.failed":
            fail_withdrawal(
                int(withdrawal_id),
                reason=(
                    data.get("failure_message")
                    or data.get("failure_code")
                    or "Stripe payout failed."
                ),
                metadata={
                    "stripe_event": event_type,
                    "stripe_status": data.get("status"),
                },
            )
            return True

        return False


provider = StripeConnectProvider()
