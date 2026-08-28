import requests
import uuid

from django.conf import settings

from .provider_base import PayoutProvider, PayoutProviderError


class MangopayProvider(PayoutProvider):
    name = "mangopay"

    def _token(self):
        client_id = getattr(
            settings,
            "MANGOPAY_CLIENT_ID",
            "",
        ).strip()

        api_key = getattr(
            settings,
            "MANGOPAY_API_KEY",
            "",
        ).strip()

        if not client_id or not api_key:
            raise PayoutProviderError(
                "MANGOPAY_CLIENT_ID/API_KEY are not configured."
            )

        base = getattr(
            settings,
            "MANGOPAY_BASE_URL",
            "https://api.mangopay.com",
        ).rstrip("/")

        response = requests.post(
            f"{base}/oauth/token",
            auth=(client_id, api_key),
            data={"grant_type": "client_credentials"},
            timeout=30,
        )

        if response.status_code >= 400:
            raise PayoutProviderError(
                response.text[:500]
            )

        return response.json()["access_token"]

    def create_recipient(self, *, user, destination):
        if not destination:
            raise PayoutProviderError(
                "Mangopay bank-account details are required."
            )

        return {
            "provider": self.name,
            "destination": destination,
        }

    def initiate(self, *, withdrawal):
        token = self._token()

        base = getattr(
            settings,
            "MANGOPAY_BASE_URL",
            "https://api.mangopay.com",
        ).rstrip("/")

        metadata = withdrawal.provider_metadata or {}
        wallet_id = metadata.get("wallet_id")
        bank_account_id = (
            withdrawal.provider_recipient
            or metadata.get("bank_account_id")
        )

        if not wallet_id:
            raise PayoutProviderError(
                "Mangopay wallet_id is required."
            )

        if not bank_account_id:
            raise PayoutProviderError(
                "Mangopay bank_account_id is required."
            )

        payload = {
            "AuthorId": str(withdrawal.user_id),
            "DebitedWalletId": wallet_id,
            "BankAccountId": bank_account_id,
            "DebitedFunds": {
                "Currency": withdrawal.currency.upper(),
                "Amount": int(withdrawal.amount * 100),
            },
            "Fees": {
                "Currency": withdrawal.currency.upper(),
                "Amount": int(withdrawal.fee * 100),
            },
            "Tag": (
                f"shopu_{withdrawal.pk}_{uuid.uuid4().hex[:16]}"
            ),
        }

        response = requests.post(
            f"{base}/v2.01/{getattr(settings, 'MANGOPAY_CLIENT_ID', '')}/payouts",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=30,
        )

        if response.status_code >= 400:
            raise PayoutProviderError(
                response.text[:500]
            )

        data = response.json()

        payout_id = data.get("Id") or data.get("id")

        if not payout_id:
            raise PayoutProviderError(
                "Mangopay returned no payout ID."
            )

        mark_withdrawal_processing(
            withdrawal.pk,
            provider_reference=str(payout_id),
            provider_recipient=str(bank_account_id),
            metadata={
                "mangopay_payout_id": payout_id,
                "mangopay_status": data.get("Status"),
            },
        )

        return data

    def verify_webhook(self, *, raw_body, signature="", headers=None):
        """
        Mangopay Hook notifications do not provide an HMAC signature
        equivalent to Paystack/Stripe/NOWPayments.

        Therefore the application must NOT claim that an arbitrary HTTP
        request is authenticated.

        Authentication is expected to be enforced at the deployment
        boundary (private endpoint, trusted proxy, mTLS, or another
        configured access-control mechanism). The Django view must pass
        only requests that have passed that boundary.
        """
        headers = headers or {}

        trusted = (
            headers.get("X-ShopU-Mangopay-Trusted")
            or headers.get("x-shopu-mangopay-trusted")
            or ""
        ).strip().lower()

        if trusted != "1":
            raise PayoutProviderError(
                "Mangopay webhook requires trusted endpoint authentication."
            )

        return True

    def handle_webhook(self, *, payload):
        event_type = str(
            payload.get("EventType")
            or payload.get("event_type")
            or ""
        ).upper()

        resource_id = str(
            payload.get("RessourceId")
            or payload.get("ResourceId")
            or ""
        ).strip()

        if not resource_id:
            return False

        if event_type in (
            "PAYOUT_NORMAL_SUCCEEDED",
            "INSTANT_PAYOUT_SUCCEEDED",
        ):
            from .models import WithdrawalRequest

            withdrawal = (
                WithdrawalRequest.objects
                .filter(
                    provider=self.name,
                    provider_reference=resource_id,
                )
                .first()
            )

            if not withdrawal:
                return False

            complete_withdrawal(
                withdrawal.pk,
                provider_reference=resource_id,
                metadata={
                    "mangopay_event": event_type,
                    "mangopay_resource_id": resource_id,
                },
            )
            return True

        if event_type in (
            "PAYOUT_NORMAL_FAILED",
            "INSTANT_PAYOUT_FAILED",
        ):
            from .models import WithdrawalRequest

            withdrawal = (
                WithdrawalRequest.objects
                .filter(
                    provider=self.name,
                    provider_reference=resource_id,
                )
                .first()
            )

            if not withdrawal:
                return False

            fail_withdrawal(
                withdrawal.pk,
                reason="Mangopay payout failed.",
                metadata={
                    "mangopay_event": event_type,
                    "mangopay_resource_id": resource_id,
                },
            )
            return True

        return False


provider = MangopayProvider()
