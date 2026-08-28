import hashlib
import hmac
import json
from decimal import Decimal
from unittest.mock import Mock, patch

from django.contrib.auth.models import User
from django.test import TestCase, override_settings

from .models import CryptoDeposit
from .nowpayments import (
    create_payment,
    process_ipn,
    verify_ipn_signature,
)
from ledger.models import LedgerTransaction


class NOWPaymentsTests(TestCase):

    def setUp(self):
        from finance.models import CryptoAssetConfig

        self.user = User.objects.create_user(
            username="crypto-user",
            password="x",
        )

        cfg, _ = CryptoAssetConfig.objects.get_or_create(
            asset="USDT"
        )
        cfg.enabled = True
        cfg.network = "TRC20"
        cfg.save()

    def _deposit(
        self,
        *,
        amount=Decimal("100"),
        pay_amount=Decimal("0.0015"),
        provider_payment_id="123",
    ):
        return CryptoDeposit.objects.create(
            user=self.user,
            asset="USDT",
            network="",
            amount=amount,
            address="T123",
            tx_hash=None,
            provider="nowpayments",
            provider_payment_id=provider_payment_id,
            price_currency="USD",
            pay_currency="usdt",
            pay_amount=pay_amount,
            payment_url="https://pay.example/123",
            metadata={},
        )

    @override_settings(
        NOWPAYMENTS_API_KEY="test-key",
        NOWPAYMENTS_IPN_SECRET="ipn-secret",
        NOWPAYMENTS_IPN_URL=(
            "https://example.com/api/crypto/"
            "nowpayments/ipn/"
        ),
    )
    @patch("crypto.nowpayments.requests.post")
    def test_create_payment(self, post):
        post.return_value = Mock(
            raise_for_status=lambda: None,
            json=lambda: {
                "payment_id": 123,
                "pay_address": "T123",
                "pay_amount": "0.0015",
                "invoice_url": (
                    "https://pay.example/123"
                ),
            },
        )

        deposit = create_payment(
            user=self.user,
            amount=Decimal("100"),
            price_currency="USD",
            pay_currency="USDT",
        )

        self.assertEqual(
            deposit.provider_payment_id,
            "123",
        )
        self.assertEqual(
            deposit.pay_amount,
            Decimal("0.0015"),
        )
        self.assertEqual(
            deposit.status,
            CryptoDeposit.PENDING,
        )
        self.assertTrue(deposit.payment_url)

        post.assert_called_once()

        request_payload = post.call_args.kwargs["json"]

        self.assertEqual(
            request_payload["price_amount"],
            100.0,
        )
        self.assertEqual(
            request_payload["price_currency"],
            "usd",
        )
        self.assertEqual(
            request_payload["pay_currency"],
            "usdt",
        )
        self.assertIn(
            "SHOPU-CRYPTO-",
            request_payload["order_id"],
        )

    @override_settings(
        NOWPAYMENTS_IPN_SECRET="secret"
    )
    def test_ipn_signature_valid(self):
        payload = {
            "payment_id": "123",
            "payment_status": "finished",
            "price_amount": 10,
            "price_currency": "usd",
        }

        body = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode()

        signature = hmac.new(
            b"secret",
            body,
            hashlib.sha512,
        ).hexdigest()

        self.assertTrue(
            verify_ipn_signature(
                payload,
                signature,
            )
        )

    @override_settings(
        NOWPAYMENTS_IPN_SECRET="secret"
    )
    def test_ipn_signature_invalid(self):
        payload = {
            "payment_id": "123",
            "payment_status": "finished",
            "price_amount": 10,
            "price_currency": "usd",
        }

        self.assertFalse(
            verify_ipn_signature(
                payload,
                "invalid-signature",
            )
        )

    def test_finished_ipn_confirms_and_credits_wallet(self):
        deposit = self._deposit()

        payload = {
            "payment_id": "123",
            "payment_status": "finished",
            "price_amount": "100",
            "price_currency": "USD",
            "pay_currency": "usdt",
            "pay_amount": "0.0015",
            "actually_paid": "0.0015",
            "payin_hash": "abc123hash",
        }

        process_ipn(payload)

        deposit.refresh_from_db()

        self.assertEqual(
            deposit.status,
            CryptoDeposit.CONFIRMED,
        )

        self.assertEqual(
            deposit.confirmations,
            1,
        )

        self.assertEqual(
            deposit.tx_hash,
            "abc123hash",
        )

        self.assertIsNotNone(
            deposit.confirmed_at
        )

    def test_finished_ipn_credits_only_once(self):
        deposit = self._deposit()

        payload = {
            "payment_id": "123",
            "payment_status": "finished",
            "price_amount": "100",
            "price_currency": "USD",
            "pay_currency": "usdt",
            "pay_amount": "0.0015",
            "actually_paid": "0.0015",
            "payin_hash": "abc123hash",
        }

        process_ipn(payload)

        first_count = LedgerTransaction.objects.filter(
            reference="CRYPTO:123"
        ).count()

        process_ipn(payload)

        second_count = LedgerTransaction.objects.filter(
            reference="CRYPTO:123"
        ).count()

        self.assertEqual(
            first_count,
            1,
        )

        self.assertEqual(
            second_count,
            1,
        )

        deposit.refresh_from_db()

        self.assertEqual(
            deposit.status,
            CryptoDeposit.CONFIRMED,
        )

    def test_finished_ipn_rejects_price_currency_mismatch(self):
        self._deposit()

        payload = {
            "payment_id": "123",
            "payment_status": "finished",
            "price_amount": "100",
            "price_currency": "EUR",
            "pay_currency": "usdt",
            "pay_amount": "0.0015",
            "actually_paid": "0.0015",
        }

        with self.assertRaisesMessage(
            ValueError,
            "price currency mismatch",
        ):
            process_ipn(payload)

        self.assertEqual(
            LedgerTransaction.objects.filter(
                reference="CRYPTO:123"
            ).count(),
            0,
        )

    def test_finished_ipn_rejects_crypto_currency_mismatch(self):
        self._deposit()

        payload = {
            "payment_id": "123",
            "payment_status": "finished",
            "price_amount": "100",
            "price_currency": "USD",
            "pay_currency": "btc",
            "pay_amount": "0.0015",
            "actually_paid": "0.0015",
        }

        with self.assertRaisesMessage(
            ValueError,
            "payment currency mismatch",
        ):
            process_ipn(payload)

        self.assertEqual(
            LedgerTransaction.objects.filter(
                reference="CRYPTO:123"
            ).count(),
            0,
        )

    def test_finished_ipn_rejects_underpayment(self):
        self._deposit(
            amount=Decimal("100"),
            pay_amount=Decimal("0.0015"),
        )

        payload = {
            "payment_id": "123",
            "payment_status": "finished",
            "price_amount": "100",
            "price_currency": "USD",
            "pay_currency": "usdt",
            "pay_amount": "0.0015",
            "actually_paid": "0.0010",
        }

        with self.assertRaisesMessage(
            ValueError,
            "amount received is below",
        ):
            process_ipn(payload)

        self.assertEqual(
            LedgerTransaction.objects.filter(
                reference="CRYPTO:123"
            ).count(),
            0,
        )

        deposit = CryptoDeposit.objects.get(
            provider_payment_id="123"
        )

        self.assertEqual(
            deposit.status,
            CryptoDeposit.PENDING,
        )

    def test_finished_ipn_rejects_underpriced_payment(self):
        self._deposit()

        payload = {
            "payment_id": "123",
            "payment_status": "finished",
            "price_amount": "99",
            "price_currency": "USD",
            "pay_currency": "usdt",
            "pay_amount": "0.0015",
            "actually_paid": "0.0015",
        }

        with self.assertRaisesMessage(
            ValueError,
            "price amount is below",
        ):
            process_ipn(payload)

        self.assertEqual(
            LedgerTransaction.objects.filter(
                reference="CRYPTO:123"
            ).count(),
            0,
        )

    def test_failed_payment_does_not_credit_wallet(self):
        deposit = self._deposit()

        payload = {
            "payment_id": "123",
            "payment_status": "failed",
            "price_amount": "100",
            "price_currency": "USD",
            "pay_currency": "usdt",
        }

        process_ipn(payload)

        deposit.refresh_from_db()

        self.assertEqual(
            deposit.status,
            CryptoDeposit.FAILED,
        )

        self.assertEqual(
            LedgerTransaction.objects.filter(
                reference="CRYPTO:123"
            ).count(),
            0,
        )

    def test_expired_payment_does_not_credit_wallet(self):
        deposit = self._deposit()

        payload = {
            "payment_id": "123",
            "payment_status": "expired",
        }

        process_ipn(payload)

        deposit.refresh_from_db()

        self.assertEqual(
            deposit.status,
            CryptoDeposit.FAILED,
        )

        self.assertEqual(
            LedgerTransaction.objects.filter(
                reference="CRYPTO:123"
            ).count(),
            0,
        )

    def test_pending_payment_does_not_credit_wallet(self):
        deposit = self._deposit()

        payload = {
            "payment_id": "123",
            "payment_status": "confirming",
        }

        process_ipn(payload)

        deposit.refresh_from_db()

        self.assertEqual(
            deposit.status,
            CryptoDeposit.PENDING,
        )

        self.assertEqual(
            LedgerTransaction.objects.filter(
                reference="CRYPTO:123"
            ).count(),
            0,
        )

    def test_unknown_payment_is_rejected(self):
        payload = {
            "payment_id": "does-not-exist",
            "payment_status": "finished",
            "price_amount": "100",
            "price_currency": "USD",
            "pay_currency": "usdt",
            "pay_amount": "0.0015",
            "actually_paid": "0.0015",
        }

        with self.assertRaisesMessage(
            ValueError,
            "Crypto payment not found",
        ):
            process_ipn(payload)

    def test_missing_payment_id_is_rejected(self):
        with self.assertRaisesMessage(
            ValueError,
            "Missing payment_id",
        ):
            process_ipn(
                {
                    "payment_status": "finished"
                }
            )

    def test_missing_payment_status_is_rejected(self):
        with self.assertRaisesMessage(
            ValueError,
            "Missing payment_status",
        ):
            process_ipn(
                {
                    "payment_id": "123"
                }
            )

    def test_confirmed_deposit_is_not_credited_again(self):
        deposit = self._deposit()

        payload = {
            "payment_id": "123",
            "payment_status": "finished",
            "price_amount": "100",
            "price_currency": "USD",
            "pay_currency": "usdt",
            "pay_amount": "0.0015",
            "actually_paid": "0.0015",
        }

        process_ipn(payload)

        deposit.refresh_from_db()

        first_confirmed_at = deposit.confirmed_at

        process_ipn(payload)

        deposit.refresh_from_db()

        self.assertEqual(
            deposit.status,
            CryptoDeposit.CONFIRMED,
        )

        self.assertEqual(
            LedgerTransaction.objects.filter(
                reference="CRYPTO:123"
            ).count(),
            1,
        )

        self.assertEqual(
            deposit.confirmed_at,
            first_confirmed_at,
        )
