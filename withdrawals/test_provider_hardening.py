from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase, override_settings

from ledger.models import LedgerTransaction
from ledger.wallet_service import credit_cash

from .models import WithdrawalRequest
from .services import (
    complete_withdrawal,
    create_withdrawal,
    fail_withdrawal,
    mark_withdrawal_processing,
)
from .mangopay_service import MangopayProvider, PayoutProviderError
from .nowpayments_service import NOWPaymentsProvider


class WithdrawalHardeningTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        from finance.models import PayoutProviderConfig

        config, _ = PayoutProviderConfig.objects.get_or_create(
            provider="paystack",
            defaults={"enabled": True},
        )
        if not config.enabled:
            config.enabled = True
            config.save(update_fields=["enabled"])

    def setUp(self):
        self.user = User.objects.create_user(
            username="withdrawal-hardening",
            password="test-password",
        )

        credit_cash(
            self.user,
            Decimal("100"),
            "USD",
            reference="TEST:CASH",
        )

    def test_processing_reference_cannot_be_replaced(self):
        withdrawal, _ = create_withdrawal(
            user=self.user,
            amount=Decimal("10"),
            currency="USD",
            provider="paystack",
        )

        mark_withdrawal_processing(
            withdrawal.pk,
            provider_reference="provider-ref-1",
        )

        with self.assertRaisesMessage(
            ValueError,
            "different provider reference",
        ):
            mark_withdrawal_processing(
                withdrawal.pk,
                provider_reference="provider-ref-2",
            )

    def test_complete_is_idempotent(self):
        withdrawal, _ = create_withdrawal(
            user=self.user,
            amount=Decimal("10"),
            currency="USD",
            provider="paystack",
        )

        mark_withdrawal_processing(
            withdrawal.pk,
            provider_reference="provider-ref",
        )

        complete_withdrawal(
            withdrawal.pk,
            provider_reference="provider-ref",
        )

        complete_withdrawal(
            withdrawal.pk,
            provider_reference="provider-ref",
        )

        self.assertEqual(
            LedgerTransaction.objects.filter(
                reference=f"WITHDRAWAL_COMPLETE:{withdrawal.pk}"
            ).count(),
            1,
        )

        withdrawal.refresh_from_db()

        self.assertEqual(
            withdrawal.status,
            WithdrawalRequest.COMPLETED,
        )

    def test_failed_withdrawal_return_is_idempotent(self):
        withdrawal, _ = create_withdrawal(
            user=self.user,
            amount=Decimal("10"),
            currency="USD",
            provider="paystack",
        )

        fail_withdrawal(
            withdrawal.pk,
            reason="provider failed",
        )

        fail_withdrawal(
            withdrawal.pk,
            reason="provider failed",
        )

        self.assertEqual(
            LedgerTransaction.objects.filter(
                reference=f"WITHDRAWAL_RETURN:{withdrawal.pk}"
            ).count(),
            1,
        )

        withdrawal.refresh_from_db()

        self.assertEqual(
            withdrawal.status,
            WithdrawalRequest.FAILED,
        )

    @override_settings(
        MANGOPAY_CLIENT_ID="test-client",
        MANGOPAY_API_KEY="test-key",
    )
    def test_mangopay_webhook_requires_trusted_boundary(self):
        provider = MangopayProvider()

        with self.assertRaises(PayoutProviderError):
            provider.verify_webhook(
                raw_body=b"{}",
                headers={},
            )

        self.assertTrue(
            provider.verify_webhook(
                raw_body=b"{}",
                headers={
                    "X-ShopU-Mangopay-Trusted": "1",
                },
            )
        )

    @override_settings(
        NOWPAYMENTS_API_KEY="test-key",
    )
    def test_nowpayments_webhook_rejects_wrong_provider(self):
        withdrawal, _ = create_withdrawal(
            user=self.user,
            amount=Decimal("10"),
            currency="USD",
            provider="paystack",
        )

        provider = NOWPaymentsProvider()

        handled = provider.handle_webhook(
            payload={
                "order_id": str(withdrawal.pk),
                "status": "finished",
                "id": "now-123",
            }
        )

        self.assertFalse(handled)

        withdrawal.refresh_from_db()

        self.assertEqual(
            withdrawal.status,
            WithdrawalRequest.PENDING,
        )
