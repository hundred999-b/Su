from django.contrib.auth import get_user_model
from django.test import TestCase

from marketplace.models import Order, Product
from stage4.models import DisputeEvent

from .models import Review
from .services import create_review


User = get_user_model()


class ReviewEligibilityTests(TestCase):
    def setUp(self):
        self.buyer = User.objects.create_user(username="review_buyer")
        self.seller = User.objects.create_user(username="review_seller")
        self.product = Product.objects.create(
            seller=self.seller,
            title="Review test product",
            description="A product used for review eligibility tests.",
            price="10.00",
            currency="USD",
        )

    def make_order(self, status):
        return Order.objects.create(
            buyer=self.buyer,
            product=self.product,
            amount="10.00",
            currency="USD",
            status=status,
        )

    def test_completed_order_can_be_reviewed(self):
        order = self.make_order(Order.COMPLETED)
        review = create_review(
            buyer=self.buyer,
            order_id=order.id,
            rating=5,
            comment="Good transaction.",
        )
        self.assertEqual(review.seller_id, self.seller.id)

    def test_disputed_order_cannot_be_reviewed_while_open(self):
        order = self.make_order(Order.DISPUTED)
        with self.assertRaises(ValueError):
            create_review(
                buyer=self.buyer,
                order_id=order.id,
                rating=5,
                comment="Too early.",
            )

    def test_buyer_favor_dispute_refund_can_be_reviewed(self):
        order = self.make_order(Order.REFUNDED)
        DisputeEvent.objects.create(
            order=order,
            actor=self.buyer,
            event_type="resolved",
            message="Buyer won the dispute.",
            metadata={"outcome": "buyer_favor", "resolution": "refund"},
        )
        review = create_review(
            buyer=self.buyer,
            order_id=order.id,
            rating=2,
            comment="The dispute was resolved in my favor.",
        )
        self.assertEqual(review.order_id, order.id)

    def test_plain_refunded_order_cannot_be_reviewed(self):
        order = self.make_order(Order.REFUNDED)
        with self.assertRaises(ValueError):
            create_review(
                buyer=self.buyer,
                order_id=order.id,
                rating=1,
                comment="Not eligible.",
            )

    def test_only_buyer_can_review(self):
        order = self.make_order(Order.COMPLETED)
        with self.assertRaises(ValueError):
            create_review(
                buyer=self.seller,
                order_id=order.id,
                rating=5,
                comment="Unauthorized.",
            )

    def test_order_cannot_be_reviewed_twice(self):
        order = self.make_order(Order.COMPLETED)
        create_review(
            buyer=self.buyer,
            order_id=order.id,
            rating=5,
            comment="First.",
        )
        with self.assertRaises(ValueError):
            create_review(
                buyer=self.buyer,
                order_id=order.id,
                rating=4,
                comment="Second.",
            )
