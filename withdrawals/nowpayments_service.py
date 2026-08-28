import hashlib
import hmac
import json
import requests

from django.conf import settings

from .provider_base import PayoutProvider, PayoutProviderError


class NOWPaymentsProvider(PayoutProvider):
    name = "nowpayments"

    def _headers(self):
        key = getattr(
            settings,
            "NOWPAYMENTS_API_KEY",
            "",
        ).strip()

        if not key:
            raise PayoutProviderError(
                "NOWPAYMENTS_API_KEY is not configured."
            )

        return {
            "x-api-key": key,
            "Content-Type": "application/json",
        }

    def create_recipient(self, *, user, destination):
        if not destination:
            raise PayoutProviderError(
                "Crypto destination is required."
            )

        return {
            "provider": self.name,
            "destination": destination,
        }

    def initiate(self, *, withdrawal):
        # NOWPayments is deliberately kept separate from fiat.
        # The currency/asset must be a configured crypto asset.
        metadata = withdrawal.provider_metadata or {}

        payout_address = (
            withdrawal.provider_recipient
            or metadata.get("payout_address")
        )

        crypto_currency = metadata.get("crypto_currency")

        if not payout_address:
            raise PayoutProviderError(
                "NOWPayments payout address is required."
            )

        if not crypto_currency:
            raise PayoutProviderError(
                "crypto_currency is required for NOWPayments."
            )

        base = getattr(
            settings,
            "NOWPAYMENTS_BASE_URL",
            "https://api.nowpayments.io/v1",
        ).rstrip("/")

        response = requests.post(
            f"{base}/payout",
            headers=self._headers(),
            json={
                "ipn_callback_url": getattr(
                    settings,
                    "NOWPAYMENTS_IPN_URL",
                    "",
                ),
                "withdrawals": [{
                    "address": payout_address,
                    "currency": crypto_currency,
                    "amount": str(withdrawal.amount),
                    "order_id": str(withdrawal.pk),
                    "order_description": (
                        f"ShopU withdrawal #{withdrawal.pk}"
                    ),
                }],
            },
            timeout=30,
        )

        if response.status_code >= 400:
            raise PayoutProviderError(
                response.text[:500]
            )

        data = response.json()

        payout_id = (
            data.get("id")
            or data.get("withdrawal_id")
        )

        if not payout_id:
            raise PayoutProviderError(
                "NOWPayments returned no payout ID."
            )

        mark_withdrawal_processing(
            withdrawal.pk,
            provider_reference=str(payout_id),
            provider_recipient=str(payout_address),
            metadata={
                "nowpayments_payout_id": payout_id,
                "nowpayments_crypto_currency": crypto_currency,
            },
        )

        return data

    def verify_webhook(self, *, raw_body, signature="", headers=None):
        secret = getattr(
            settings,
            "NOWPAYMENTS_IPN_SECRET",
            "",
        ).strip()

        if not secret:
            raise PayoutProviderError(
                "NOWPAYMENTS_IPN_SECRET is not configured."
            )

        headers = headers or {}

        supplied = (
            signature
            or headers.get("x-nowpayments-sig")
            or headers.get("X-Nowpayments-Sig")
            or ""
        ).strip()

        if not supplied:
            raise PayoutProviderError(
                "NOWPayments IPN signature is missing."
            )

        try:
            payload = json.loads(
                raw_body.decode("utf-8")
            )
        except Exception as exc:
            raise PayoutProviderError(
                "Invalid NOWPayments IPN JSON."
            ) from exc

        canonical = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")

        expected = hmac.new(
            secret.encode("utf-8"),
            canonical,
            hashlib.sha512,
        ).hexdigest()

        if not hmac.compare_digest(
            expected,
            supplied,
        ):
            raise PayoutProviderError(
                "Invalid NOWPayments IPN signature."
            )

        return True

    def handle_webhook(self, *, payload):
        withdrawal_id = payload.get("order_id")

        if not withdrawal_id:
            withdrawal_id = (
                payload.get("withdrawal_id")
                or payload.get("shopu_withdrawal_id")
            )

        if not withdrawal_id:
            return False

        from .models import WithdrawalRequest

        withdrawal = (
            WithdrawalRequest.objects
            .filter(
                pk=withdrawal_id,
                provider=WithdrawalRequest.PROVIDER_NOWPAYMENTS,
            )
            .first()
        )

        if not withdrawal:
            return False

        status = str(
            payload.get("status", "")
        ).lower()

        if status in (
            "finished",
            "confirmed",
            "completed",
        ):
            complete_withdrawal(
                int(withdrawal_id),
                provider_reference=str(
                    payload.get("id")
                    or payload.get("withdrawal_id")
                    or ""
                ),
                metadata={
                    "nowpayments_status": status,
                },
            )
            return True

        if status in (
            "failed",
            "refunded",
            "expired",
        ):
            fail_withdrawal(
                int(withdrawal_id),
                reason=(
                    payload.get("error")
                    or "NOWPayments payout failed."
                ),
                metadata={
                    "nowpayments_status": status,
                },
            )
            return True

        return False


provider = NOWPaymentsProvider()
