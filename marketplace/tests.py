from decimal import Decimal
from django.contrib.auth.models import User
from django.test import TestCase
from .models import Product, ListingVersion, Order
from .services import publish_listing, get_active_listing_policy
from stage4.models import TermsDocument, TermsAcceptance


class ListingEvidenceTests(TestCase):
    def setUp(self):
        self.seller = User.objects.create_user("seller", password="x")
        self.buyer = User.objects.create_user("buyer", password="x")

        # Stage 4: create and accept the active Seller Terms
        # inside the temporary Django test database.
        self.seller_terms = TermsDocument.objects.create(
            kind=TermsDocument.SELLER,
            version="1.0",
            title="ShopU Seller Terms",
            body="Test seller terms.",
            active=True,
            created_by=self.seller,
        )

        TermsAcceptance.objects.create(
            user=self.seller,
            terms=self.seller_terms,
            purpose="listing",
        )

    def listing(self):
        return {
            "title": "Used laptop",
            "description": "Used laptop in good working condition. Screen has a small scratch and charger is included.",
            "category": "Electronics",
            "condition": "Used",
            "seller_terms": "Buyer receives the item as described.",
            "price": Decimal("100.00"),
            "currency": "USD",
            "disclosure_acknowledged": True,
            "fee_acknowledged": True,
        }

    def test_listing_requires_full_disclosure_acknowledgment(self):
        data = self.listing()
        data["disclosure_acknowledged"] = False
        with self.assertRaises(ValueError):
            publish_listing(seller=self.seller, data=data)

    def test_publish_creates_immutable_version(self):
        product = publish_listing(seller=self.seller, data=self.listing())
        self.assertEqual(product.version, 1)
        self.assertEqual(ListingVersion.objects.filter(product=product).count(), 1)
        self.assertEqual(get_active_listing_policy().version, 1)


class MarketplacePurchaseFlowTests(TestCase):
    def setUp(self):
        from ledger.wallet_service import credit_cash
        self.seller = User.objects.create_user("seller2", password="x")
        self.buyer = User.objects.create_user("buyer2", password="x")
        self.seller_terms = TermsDocument.objects.create(
            kind=TermsDocument.SELLER, version="1.0", title="Seller",
            body="Seller terms", active=True, created_by=self.seller,
        )
        self.buyer_terms = TermsDocument.objects.create(
            kind=TermsDocument.BUYER, version="1.0", title="Buyer",
            body="Buyer terms", active=True, created_by=self.seller,
        )
        TermsAcceptance.objects.create(
            user=self.seller, terms=self.seller_terms, purpose="listing"
        )
        TermsAcceptance.objects.create(
            user=self.buyer, terms=self.buyer_terms, purpose="purchase"
        )
        self.product = publish_listing(
            seller=self.seller,
            data={
                "title": "Laptop",
                "description": "A properly described used laptop with charger and minor wear.",
                "category": "Electronics",
                "condition": "Used",
                "seller_terms": "Sold as described.",
                "price": Decimal("20.00"),
                "currency": "USD",
                "disclosure_acknowledged": True,
                "fee_acknowledged": True,
            },
        )
        credit_cash(
            self.buyer, Decimal("50.00"), "USD",
            reference="BUYER_PURCHASE_FUNDS"
        )

    def test_purchase_creates_stage4_snapshot(self):
        from .services import purchase_product
        from stage4.models import OrderListingSnapshot
        order, tx = purchase_product(
            buyer=self.buyer, product_id=self.product.id,
            disclosure_acknowledged=True,
        )
        self.assertEqual(order.status, Order.ESCROW)
        self.assertTrue(
            OrderListingSnapshot.objects.filter(order=order).exists()
        )
        snapshot = OrderListingSnapshot.objects.get(order=order)
        self.assertEqual(snapshot.listing_version.version, self.product.version)

    def test_buyer_cannot_confirm_before_delivery(self):
        from .services import purchase_product, confirm_order
        order, _ = purchase_product(
            buyer=self.buyer, product_id=self.product.id,
            disclosure_acknowledged=True,
        )
        with self.assertRaises(ValueError):
            confirm_order(order_id=order.id, buyer=self.buyer)

    def test_buyer_can_confirm_after_delivery(self):
        from .services import (
            purchase_product, mark_order_delivered, confirm_order
        )
        order, _ = purchase_product(
            buyer=self.buyer, product_id=self.product.id,
            disclosure_acknowledged=True,
        )
        mark_order_delivered(
            order_id=order.id, seller=self.seller, auto_release_hours=6
        )
        order, tx = confirm_order(order_id=order.id, buyer=self.buyer)
        order.refresh_from_db()
        self.assertEqual(order.status, Order.COMPLETED)
        self.assertIsNotNone(tx)


    def test_purchase_idempotency_prevents_duplicate_escrow(self):
        from .services import purchase_product
        from escrow.models import Escrow
        first, tx1 = purchase_product(
            buyer=self.buyer, product_id=self.product.id,
            disclosure_acknowledged=True, idempotency_key="same-request",
        )
        second, tx2 = purchase_product(
            buyer=self.buyer, product_id=self.product.id,
            disclosure_acknowledged=True, idempotency_key="same-request",
        )
        self.assertEqual(first.id, second.id)
        self.assertEqual(tx1.transaction_id, tx2.transaction_id)
        self.assertEqual(Escrow.objects.filter(order=first).count(), 1)

class VendorProfileDisputeMetricTests(TestCase):
    def test_dispute_count_is_recorded_as_vendor_metric(self):
        from stage4.models import DisputeEvent
        seller = User.objects.create_user(username="dispute_seller")
        buyer = User.objects.create_user(username="dispute_buyer")
        product = Product.objects.create(seller=seller, title="Test", description="A test listing with enough description content for the model.", category="Test", price=Decimal("10"), currency="USD", active=True)
        order = Order.objects.create(product=product, buyer=buyer, amount=Decimal("10"), currency="USD", status=Order.DISPUTED)
        DisputeEvent.objects.create(order=order, actor=buyer, event_type="opened", message="issue")
        self.assertEqual(DisputeEvent.objects.filter(order__product__seller=seller, event_type="opened").count(), 1)
