from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase

from ledger.transaction_service import purchase_order
from ledger.wallet_service import credit_cash, wallet_balance
from marketplace.models import Product, Order
from escrow.services import release_escrow
from .models import ReferralProfile, ReferralProgramSettings, ReferralReward
from .services import attribute_referral


class ReferralTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            username="referral_test_admin",
            email="referral_test_admin@example.com",
            password="test-password",
        )
        program = ReferralProgramSettings.get_solo()
        program.enabled = True
        program.transactions_limit = 10
        program.commission_percent = Decimal("0.5000")
        program.save()

        self.referrer = User.objects.create_user(username="referrer", password="x")
        self.buyer = User.objects.create_user(username="buyer", password="x")
        credit_cash(self.buyer, Decimal("1000.00"), "USD", reference="TEST_REFERRAL_DEPOSIT")
        self.referral = ReferralProfile.objects.create(user=self.referrer)
        attribute_referral(self.buyer, self.referral.code)

    def make_completed_order(self, amount):
        product = Product.objects.create(
            seller=self.referrer, title="Test", description="Test",
            price=amount, currency="USD", active=True,
        )
        order = Order.objects.create(
            buyer=self.buyer, product=product, amount=amount,
            currency="USD", status=Order.PENDING,
        )
        purchase_order(order)
        release_escrow(order.escrow.id, actor=self.admin, reason="test")
        return order

    def test_first_ten_transactions_are_rewarded(self):
        for _ in range(10):
            self.make_completed_order(Decimal("10.00"))
        buyer_referral = ReferralProfile.objects.get(user=self.buyer)
        self.assertEqual(buyer_referral.eligible_transactions_count, 10)
        self.assertEqual(ReferralReward.objects.filter(referrer=self.referrer).count(), 10)
        self.assertEqual(buyer_referral.total_earned_by_currency["USD"], "0.50")
        self.assertEqual(wallet_balance(self.referrer, "USD"), Decimal("0.50"))

        self.make_completed_order(Decimal("10.00"))
        self.assertEqual(ReferralReward.objects.filter(referrer=self.referrer).count(), 10)

    def test_self_referral_is_ignored(self):
        profile = ReferralProfile.objects.create(
            user=User.objects.create_user(username="other", password="x")
        )
        attribute_referral(profile.user, profile.code)
        profile.refresh_from_db()
        self.assertIsNone(profile.referred_by_id)

    def test_referral_cannot_be_added_after_completed_transaction(self):
        referred = User.objects.create_user(username="late_buyer", password="x")
        product = Product.objects.create(
            seller=self.referrer, title="Late", description="Late",
            price=Decimal("5.00"), currency="USD", active=True,
        )
        credit_cash(referred, Decimal("20.00"), "USD", reference="LATE_DEPOSIT")
        order = Order.objects.create(
            buyer=referred, product=product, amount=Decimal("5.00"),
            currency="USD", status=Order.PENDING,
        )
        purchase_order(order)
        release_escrow(order.escrow.id, actor=self.admin, reason="test")
        profile = attribute_referral(referred, self.referral.code)
        self.assertIsNone(profile.referred_by_id)
