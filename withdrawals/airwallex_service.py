import hashlib
import hmac
import time
import requests
import uuid

from django.conf import settings

from .provider_base import PayoutProvider, PayoutProviderError


class AirwallexProvider(PayoutProvider):
    name = "airwallex"

    def _token(self):
        base = getattr(
            settings,
            "AIRWALLEX_BASE_URL",
            "https://api.airwallex.com",
        ).rstrip("/")

        client_id = getattr(
            settings,
            "AIRWALLEX_CLIENT_ID",
            "",
        ).strip()

        api_key = getattr(
            settings,
            "AIRWALLEX_API_KEY",
            "",
        ).strip()

        if not client_id or not api_key:
            raise PayoutProviderError(
                "AIRWALLEX_CLIENT_ID/API_KEY are not configured."
            )

        response = requests.post(
            f"{base}/api/v1/authentication/login",
            headers={
                "x-client-id": client_id,
                "x-api-key": api_key,
            },
            timeout=30,
        )

        if response.status_code >= 400:
            raise PayoutProviderError(
                response.text[:500]
            )

        return response.json()["token"]

    def create_recipient(self, *, user, destination):
        # Airwallex beneficiary creation is kept provider-specific.
        # destination is stored in provider_metadata and never exposed
        # through the generic WithdrawalRequest API.
        if not destination:
            raise PayoutProviderError(
                "Airwallex beneficiary details are required."
            )

        return {
            "provider": self.name,
            "destination": destination,
        }

    def initiate(self, *, withdrawal):
        token = self._token()

        base = getattr(
            settings,
            "AIRWALLEX_BASE_URL",
            "https://api.airwallex.com",
        ).rstrip("/")

        metadata = withdrawal.provider_metadata or {}
        beneficiary_id = (
            withdrawal.provider_recipient
            or metadata.get("beneficiary_id")
        )

        if not beneficiary_id:
            raise PayoutProviderError(
                "Airwallex beneficiary_id is required."
            )

        reference = (
            f"shopu_{withdrawal.pk}_{uuid.uuid4().hex[:20]}"
        )

        response = requests.post(
            f"{base}/api/v1/transfers/create",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            json={
                "request_id": reference,
                "beneficiary_id": beneficiary_id,
                "amount": float(withdrawal.amount),
                "currency": withdrawal.currency.upper(),
                "reason": f"ShopU withdrawal #{withdrawal.pk}",
            },
            timeout=30,
        )

        if response.status_code >= 400:
            raise PayoutProviderError(
                response.text[:500]
            )

        data = response.json()

        transfer_id = (
            data.get("id")
            or data.get("transfer_id")
        )

        if not transfer_id:
            raise PayoutProviderError(
                "Airwallex returned no transfer ID."
            )

        mark_withdrawal_processing(
            withdrawal.pk,
            provider_reference=str(transfer_id),
            provider_recipient=str(beneficiary_id),
            metadata={
                "airwallex_transfer_id": transfer_id,
                "airwallex_request_id": reference,
            },
        )

        return data

    def verify_webhook(self, *, raw_body, signature="", headers=None):
        secret = getattr(
            settings,
            "AIRWALLEX_WEBHOOK_SECRET",
            "",
        ).strip()

        if not secret:
            raise PayoutProviderError(
                "AIRWALLEX_WEBHOOK_SECRET is not configured."
            )

        headers = headers or {}

        timestamp = (
            headers.get("x-timestamp")
            or headers.get("X-Timestamp")
            or ""
        ).strip()

        supplied = (
            signature
            or headers.get("x-signature")
            or headers.get("X-Signature")
            or ""
        ).strip()

        if not timestamp or not supplied:
            raise PayoutProviderError(
                "Airwallex webhook signature is missing."
            )

        try:
            timestamp_int = int(timestamp)
        except ValueError as exc:
            raise PayoutProviderError(
                "Invalid Airwallex webhook timestamp."
            ) from exc

        now_ms = int(time.time() * 1000)

        if abs(now_ms - timestamp_int) > 300000:
            raise PayoutProviderError(
                "Airwallex webhook timestamp expired."
            )

        message = (
            timestamp.encode("utf-8")
            + raw_body
        )

        expected = hmac.new(
            secret.encode("utf-8"),
            message,
            hashlib.sha256,
        ).hexdigest()

        if not hmac.compare_digest(
            expected,
            supplied,
        ):
            raise PayoutProviderError(
                "Invalid Airwallex webhook signature."
            )

        return True

    def handle_webhook(self, *, payload):
        event_id = payload.get("id")

        if not event_id:
            return False

        data = payload.get("data") or {}
        metadata = data.get("metadata") or {}

        withdrawal_id = (
            metadata.get("shopu_withdrawal_id")
            or data.get("shopu_withdrawal_id")
        )

        if not withdrawal_id:
            return False

        event_type = (
            payload.get("name")
            or payload.get("event_type")
            or ""
        ).lower()

        if "succeeded" in event_type or "success" in event_type:
            complete_withdrawal(
                int(withdrawal_id),
                provider_reference=str(
                    data.get("id")
                    or data.get("transfer_id")
                    or ""
                ),
                metadata={
                    "airwallex_event_id": event_id,
                    "airwallex_event": event_type,
                },
            )
            return True

        if "failed" in event_type or "cancelled" in event_type:
            fail_withdrawal(
                int(withdrawal_id),
                reason=str(
                    data.get("failure_reason")
                    or data.get("reason")
                    or "Airwallex payout failed."
                ),
                metadata={
                    "airwallex_event_id": event_id,
                    "airwallex_event": event_type,
                },
            )
            return True

        return False


provider = AirwallexProvider()
