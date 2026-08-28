from django.contrib.auth.models import User
from django.test import TestCase

from .models import VendorVerification, VerificationProgramSettings
from .services import apply_for_verification, set_vendor_status


class VendorVerificationTests(TestCase):
    def test_verification_is_optional_for_seller(self):
        seller = User.objects.create_user(username="seller")
        self.assertFalse(VendorVerification.objects.filter(seller=seller).exists())

    def test_admin_can_configure_requirements_and_approve(self):
        seller = User.objects.create_user(username="seller")
        settings = VerificationProgramSettings.get_solo()
        settings.require_identity = True
        settings.require_business = False
        settings.require_payment_history = False
        settings.require_transaction_history = False
        settings.minimum_completed_transactions = 0
        settings.save()

        verification = apply_for_verification(seller)
        self.assertEqual(verification.status, VendorVerification.PENDING)

        verification.identity_verified = True
        verification.save(update_fields=["identity_verified"])
        approved = set_vendor_status(
            seller, VendorVerification.VERIFIED, reviewer=seller
        )
        self.assertEqual(approved.status, VendorVerification.VERIFIED)

    def test_admin_can_add_custom_required_step(self):
        from .models import VerificationStep, VerificationStepResult
        from .services import apply_for_verification, set_step_result
        seller = User.objects.create_user(username="customseller")
        step = VerificationStep.objects.create(key="phone_check", name="Phone ownership", required=True, enabled=True)
        verification = apply_for_verification(seller)
        self.assertTrue(VerificationStepResult.objects.filter(verification=verification, step=step).exists())
        self.assertFalse(__import__('vendor_verification.services', fromlist=['verification_requirements_met']).verification_requirements_met(seller))
        set_step_result(verification_id=verification.id, step_id=step.id, status=VerificationStepResult.PASSED, reviewer=seller)

class VendorTrustSignalTests(TestCase):
    def setUp(self):
        from django.contrib.auth.models import User
        from marketplace.models import Product, Order
        self.seller = User.objects.create_user(username="trustseller")
        self.buyer = User.objects.create_user(username="trustbuyer")
        self.product = Product.objects.create(
            seller=self.seller, title="Test", description="A sufficiently described test product", price="10", currency="USD"
        )
        self.order = Order.objects.create(
            buyer=self.buyer, product=self.product, amount="10", currency="USD", status=Order.COMPLETED
        )

    def test_trusted_badge_is_admin_reliability_designation(self):
        from .models import VendorVerification
        from .services import set_vendor_status
        from .trust import vendor_badges
        verification = set_vendor_status(
            self.seller, VendorVerification.TRUSTED, reviewer=self.buyer, note="Consistently reliable seller"
        )
        self.assertEqual(verification.status, VendorVerification.TRUSTED)
        self.assertEqual(vendor_badges(self.seller)["primary"]["key"], "trusted")

    def test_verified_badge_requires_verification_process(self):
        from .models import VendorVerification
        from .services import set_vendor_status
        with self.assertRaises(ValueError):
            set_vendor_status(self.seller, VendorVerification.VERIFIED, reviewer=self.buyer)

    def test_disputes_trigger_caution(self):
        from stage4.models import DisputeEvent
        from .trust import vendor_badges
        DisputeEvent.objects.create(order=self.order, actor=self.buyer, event_type="opened", message="issue")
        DisputeEvent.objects.create(order=self.order, actor=self.buyer, event_type="opened", message="duplicate event")
        self.assertTrue(vendor_badges(self.seller)["caution"])
        self.assertTrue(vendor_badges(self.seller)["caution_reasons"])

    def test_complaint_can_trigger_caution(self):
        from .models import VendorComplaint, VendorTrustSettings
        from .trust import vendor_badges
        settings = VendorTrustSettings.get_solo()
        settings.caution_complaint_threshold = 1
        settings.save()
        VendorComplaint.objects.create(seller=self.seller, reporter=self.buyer, description="A complaint that needs review", status=VendorComplaint.OPEN)
        self.assertTrue(vendor_badges(self.seller)["caution"])

    def test_admin_override_can_clear_automatic_caution(self):
        from stage4.models import DisputeEvent
        from .models import VendorVerification
        from .trust import vendor_badges
        DisputeEvent.objects.create(order=self.order, actor=self.buyer, event_type="opened", message="issue")
        verification = VendorVerification.objects.create(seller=self.seller, caution_override=False)
        self.assertFalse(vendor_badges(self.seller)["caution"])
        verification.caution_override = True
        verification.save(update_fields=["caution_override", "updated_at"])
        self.assertTrue(vendor_badges(self.seller)["caution"])
