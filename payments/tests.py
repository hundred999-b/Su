from decimal import Decimal
from unittest.mock import Mock, patch

from django.contrib.auth.models import User
from django.test import TestCase, override_settings

from ledger.wallet_service import wallet_balance
from .models import Payment
from .services import initialize_paystack_payment, verify_paystack_payment


class PaystackPaymentTests(TestCase):
    @override_settings(
        PAYSTACK_SECRET_KEY="sk_test_example",
        PAYSTACK_CURRENCY="NGN",
        PAYSTACK_ALLOWED_CURRENCIES=["NGN"],
        PAYSTACK_CALLBACK_URL="https://example.com/payment/callback",
    )
    @patch("payments.services.requests.post")
    def test_initialize_payment(self, post):
        post.return_value = Mock(
            raise_for_status=lambda: None,
            json=lambda: {
                "status": True,
                "data": {
                    "authorization_url": "https://checkout.paystack.com/test",
                    "access_code": "abc123",
                    "reference": "ignored",
                },
            },
        )
        user = User.objects.create_user(username="payer", email="payer@example.com")
        payment = initialize_paystack_payment(
            user=user, amount=Decimal("100.00"), currency="NGN"
        )
        self.assertEqual(payment.provider, "paystack")
        self.assertEqual(payment.status, Payment.PENDING)
        self.assertTrue(payment.authorization_url)
        self.assertTrue(post.called)
        payload = post.call_args.kwargs["json"]
        self.assertEqual(payload["amount"], 10000)
        self.assertEqual(payload["currency"], "NGN")

    @override_settings(
        PAYSTACK_SECRET_KEY="sk_test_example",
        PAYSTACK_CURRENCY="NGN",
        PAYSTACK_ALLOWED_CURRENCIES=["NGN"],
        PAYSTACK_CALLBACK_URL="https://example.com/payment/callback",
    )
    @patch("payments.services.requests.get")
    def test_successful_verification_credits_wallet_once(self, get):
        get.return_value = Mock(
            raise_for_status=lambda: None,
            json=lambda: {
                "status": True,
                "data": {
                    "status": "success",
                    "amount": 10000,
                    "currency": "NGN",
                },
            },
        )
        user = User.objects.create_user(username="payer", email="payer@example.com")
        payment = Payment.objects.create(
            user=user,
            provider="paystack",
            provider_reference="SHOPU-TEST",
            amount=Decimal("100.00"),
            currency="NGN",
            idempotency_key="SHOPU-TEST",
        )
        verify_paystack_payment("SHOPU-TEST")
        self.assertEqual(wallet_balance(user, "NGN"), Decimal("100.00"))
        verify_paystack_payment("SHOPU-TEST")
        self.assertEqual(wallet_balance(user, "NGN"), Decimal("100.00"))

    def test_gift_card_payment_does_not_credit_cash_wallet(self):
        from giftcards.models import GiftCard, GiftCardPurchase
        from .services import mark_succeeded
        user = User.objects.create_user(username="giftpayer", email="giftpayer@example.com")
        payment = Payment.objects.create(
            user=user, provider="paystack", provider_reference="GIFT-TEST",
            amount=Decimal("50.00"), currency="USD", idempotency_key="GIFT-TEST",
            metadata={"purpose": "gift_card"},
        )
        card = GiftCard.objects.create(code="TESTGIFTCARD", currency="USD", initial_amount=Decimal("50"), remaining_amount=Decimal("50"), status=GiftCard.DISABLED)
        purchase = GiftCardPurchase.objects.create(buyer=user, gift_card=card, payment=payment, amount=Decimal("50"), currency="USD")
        payment.metadata["gift_card_purchase_id"] = purchase.id
        payment.save(update_fields=["metadata"])
        mark_succeeded(payment.id, provider_reference="GIFT-TEST")
        card.refresh_from_db(); purchase.refresh_from_db()
        self.assertEqual(card.status, GiftCard.ACTIVE)
        self.assertEqual(purchase.status, GiftCardPurchase.PAID)
        self.assertEqual(wallet_balance(user, "USD"), Decimal("0.00"))
