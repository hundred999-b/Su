from decimal import Decimal

from django.contrib.auth.models import User, Permission
from django.test import TestCase, override_settings

from ledger.models import LedgerAccount
from ledger.transaction_service import purchase_order
from ledger.wallet_service import ensure_wallet, credit_cash

from marketplace.models import Product, Order
from escrow.models import Escrow
from escrow.services import release_escrow, refund_escrow


class EscrowAuthorizationTests(TestCase):

    def setUp(self):
        # -------------------------------------------------
        # SYSTEM FINANCIAL ACCOUNTS
        # -------------------------------------------------
        LedgerAccount.objects.get_or_create(
            name="ESCROW",
            currency="USD",
            defaults={
                "account_type": LedgerAccount.LIABILITY,
            },
        )

        LedgerAccount.objects.get_or_create(
            name="PLATFORM_REVENUE",
            currency="USD",
            defaults={
                "account_type": LedgerAccount.REVENUE,
            },
        )

        LedgerAccount.objects.get_or_create(
            name="PAYMENT_CLEARING",
            currency="USD",
            defaults={
                "account_type": LedgerAccount.ASSET,
            },
        )

        # -------------------------------------------------
        # USERS
        # -------------------------------------------------
        self.buyer = User.objects.create_user(
            username="escrow_test_buyer",
            password="test-password",
        )

        self.seller = User.objects.create_user(
            username="escrow_test_seller",
            password="test-password",
        )

        self.admin = User.objects.create_user(
            username="escrow_test_admin",
            password="test-password",
            is_staff=True,
            is_superuser=True,
        )

        # Explicit settlement permission
        permission = Permission.objects.get(
            codename="settle_escrow",
            content_type__app_label="escrow",
        )
        self.admin.user_permissions.add(permission)

        # -------------------------------------------------
        # WALLET ACCOUNTS
        # -------------------------------------------------
        ensure_wallet(self.buyer, "USD")
        ensure_wallet(self.seller, "USD")

        # Give buyer enough test funds
        credit_cash(
            self.buyer,
            Decimal("100.00"),
            currency="USD",
            reference="TEST_ESCROW_FUNDING",
            metadata={"test": True},
        )

        # -------------------------------------------------
        # PRODUCT / ORDER
        # -------------------------------------------------
        self.product = Product.objects.create(
            seller=self.seller,
            title="Escrow Authorization Test Product",
            description="Test product",
            price=Decimal("5.00"),
            currency="USD",
            active=True,
        )

        self.order = Order.objects.create(
            buyer=self.buyer,
            product=self.product,
            amount=Decimal("5.00"),
            currency="USD",
            status=Order.PENDING,
        )

        # Real purchase path
        purchase_order(self.order)

        self.escrow = Escrow.objects.get(
            order=self.order
        )

    # -----------------------------------------------------
    # TESTS
    # -----------------------------------------------------

    def test_admin_can_release(self):
        tx = release_escrow(
            self.escrow.id,
            actor=self.admin,
            reason="admin_test",
        )

        self.escrow.refresh_from_db()
        self.order.refresh_from_db()

        self.assertIsNotNone(tx)
        self.assertEqual(self.escrow.status, Escrow.RELEASED)
        self.assertEqual(self.order.status, Order.COMPLETED)

    def test_buyer_cannot_release(self):
        with self.assertRaises(PermissionError):
            release_escrow(
                self.escrow.id,
                actor=self.buyer,
            )

        self.escrow.refresh_from_db()
        self.assertEqual(self.escrow.status, Escrow.HOLDING)

    def test_buyer_cannot_refund(self):
        with self.assertRaises(PermissionError):
            refund_escrow(
                self.escrow.id,
                actor=self.buyer,
            )

        self.escrow.refresh_from_db()
        self.assertEqual(self.escrow.status, Escrow.HOLDING)

    def test_seller_cannot_release(self):
        with self.assertRaises(PermissionError):
            release_escrow(
                self.escrow.id,
                actor=self.seller,
            )

        self.escrow.refresh_from_db()
        self.assertEqual(self.escrow.status, Escrow.HOLDING)

    def test_seller_cannot_refund(self):
        with self.assertRaises(PermissionError):
            refund_escrow(
                self.escrow.id,
                actor=self.seller,
            )

        self.escrow.refresh_from_db()
        self.assertEqual(self.escrow.status, Escrow.HOLDING)

    def test_duplicate_release_blocked(self):
        release_escrow(
            self.escrow.id,
            actor=self.admin,
            reason="first_release",
        )

        with self.assertRaises(ValueError):
            release_escrow(
                self.escrow.id,
                actor=self.admin,
                reason="duplicate_release",
            )

    def test_release_then_refund_blocked(self):
        release_escrow(
            self.escrow.id,
            actor=self.admin,
            reason="release_then_refund_test",
        )

        with self.assertRaises(ValueError):
            refund_escrow(
                self.escrow.id,
                actor=self.admin,
            )

    def test_failed_unauthorized_attacks_do_not_move_money(self):
        buyer_before = self.buyer_balance()
        seller_before = self.seller_balance()

        for actor, operation in [
            (self.buyer, release_escrow),
            (self.buyer, refund_escrow),
            (self.seller, release_escrow),
            (self.seller, refund_escrow),
        ]:
            with self.assertRaises(PermissionError):
                operation(
                    self.escrow.id,
                    actor=actor,
                )

        self.escrow.refresh_from_db()

        self.assertEqual(
            self.escrow.status,
            Escrow.HOLDING,
        )

        self.assertEqual(
            self.buyer_balance(),
            buyer_before,
        )

        self.assertEqual(
            self.seller_balance(),
            seller_before,
        )

    def buyer_balance(self):
        from ledger.services import account_balance

        account = ensure_wallet(
            self.buyer,
            "USD",
        ).ledger_account

        return account_balance(account)

    def seller_balance(self):
        from ledger.services import account_balance

        account, _ = LedgerAccount.objects.get_or_create(
            name=f"SELLER:{self.seller.id}",
            currency="USD",
            defaults={
                "account_type": LedgerAccount.LIABILITY,
            },
        )

        return account_balance(account)


@override_settings(SECURE_SSL_REDIRECT=False)
class PrivateEscrowAccessSecurityTests(TestCase):

    def setUp(self):
        from unittest.mock import patch
        from escrow.models import PrivateEscrow

        self.patch_auth = patch(
            "telegram_integration.miniapp_api.authenticate_init_data"
        )
        self.auth = self.patch_auth.start()
        self.addCleanup(self.patch_auth.stop)

        self.seller = User.objects.create_user(
            username="private_seller",
            password="test",
        )
        self.buyer = User.objects.create_user(
            username="private_buyer",
            password="test",
        )
        self.stranger = User.objects.create_user(
            username="private_stranger",
            password="test",
        )

        self.escrow = PrivateEscrow.objects.create(
            escrow_id="SU-SECURITYTEST",
            seller=self.seller,
            title="Private transaction",
            description="Sensitive transaction details",
            amount=Decimal("25.00"),
            currency="USD",
        )

        from django.test import Client
        self.client = Client()

    def test_stranger_cannot_view_private_escrow(self):
        from telegram_integration.miniapp_api import private_escrow

        self.auth.return_value = self.stranger

        response = self.client.get(
            "/miniapp/escrow/SU-SECURITYTEST/"
        )

        self.assertEqual(response.status_code, 404)
        self.assertNotIn(
            b"Sensitive transaction details",
            response.content,
        )

    def test_unauthenticated_user_cannot_view_private_escrow(self):
        self.auth.return_value = None

        response = self.client.get(
            "/miniapp/escrow/SU-SECURITYTEST/"
        )

        self.assertEqual(response.status_code, 401)

    def test_seller_can_view_private_escrow(self):
        self.auth.return_value = self.seller

        response = self.client.get(
            "/miniapp/escrow/SU-SECURITYTEST/"
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn(
            b"Sensitive transaction details",
            response.content,
        )

    def test_joined_buyer_can_view_private_escrow(self):
        self.escrow.buyer = self.buyer
        self.escrow.save(update_fields=["buyer"])

        self.auth.return_value = self.buyer

        response = self.client.get(
            "/miniapp/escrow/SU-SECURITYTEST/"
        )

        self.assertEqual(response.status_code, 200)

    def test_stranger_cannot_join_already_joined_escrow(self):
        self.escrow.buyer = self.buyer
        self.escrow.save(update_fields=["buyer"])

        self.auth.return_value = self.stranger

        response = self.client.post(
            "/miniapp/escrow/SU-SECURITYTEST/join/",
            {"init_data": "test"},
        )

        self.assertEqual(response.status_code, 404)
