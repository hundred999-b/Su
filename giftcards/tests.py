from decimal import Decimal
from django.contrib.auth.models import User
from django.test import TestCase
from .models import GiftCardTopUp
from .services import submit_gift_card_topup, review_gift_card_topup
from ledger.wallet_service import gift_balance

class GiftCardTopUpTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("giftbuyer", password="x")
        self.staff = User.objects.create_user("giftstaff", password="x", is_staff=True)

    def test_submission_is_pending_and_does_not_credit_wallet(self):
        topup = submit_gift_card_topup(user=self.user, brand="Apple", code="APPLE-123456", claimed_amount=25, claimed_currency="USD")
        self.assertEqual(topup.status, GiftCardTopUp.PENDING)
        self.assertEqual(gift_balance(self.user, "USD"), Decimal("0.00"))

    def test_approval_credits_non_withdrawable_gift_balance_once(self):
        topup = submit_gift_card_topup(user=self.user, brand="Apple", code="APPLE-654321", claimed_amount=25, claimed_currency="USD")
        review_gift_card_topup(topup_id=topup.id, reviewer=self.staff, status=GiftCardTopUp.APPROVED, approved_amount=20, approved_currency="USD")
        self.assertEqual(gift_balance(self.user, "USD"), Decimal("20.00"))
        review_gift_card_topup(topup_id=topup.id, reviewer=self.staff, status=GiftCardTopUp.APPROVED, approved_amount=20, approved_currency="USD")
        self.assertEqual(gift_balance(self.user, "USD"), Decimal("20.00"))

    def test_duplicate_code_rejected(self):
        submit_gift_card_topup(user=self.user, brand="Apple", code="APPLE-DUPLICATE", claimed_amount=10, claimed_currency="USD")
        with self.assertRaises(ValueError):
            submit_gift_card_topup(user=self.user, brand="Apple", code="apple-duplicate", claimed_amount=10, claimed_currency="USD")
