from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, TransactionTestCase

from finance.models import FinanceSettings
from ledger.models import LedgerAccount
from ledger.services import account_balance
from ledger.wallet_service import credit_cash, ensure_wallet

from .models import WithdrawalRequest
from .services import (
    create_withdrawal,
    complete_withdrawal,
    fail_withdrawal,
)


User = get_user_model()


class WithdrawalSecurityTests(TransactionTestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            username="withdrawal_test_user"
        )

        self.attacker = User.objects.create_user(
            username="withdrawal_attacker"
        )

        settings = FinanceSettings.get_solo()
        settings.min_withdrawal = Decimal("1.00")
        settings.max_withdrawal = Decimal("1000.00")
        settings.withdrawal_fee = Decimal("1.00")
        settings.save()

        ensure_wallet(self.user, "USD")
        ensure_wallet(self.attacker, "USD")

        credit_cash(
            self.user,
            Decimal("20.00"),
            currency="USD",
            reference="TEST_WITHDRAWAL_DEPOSIT",
            metadata={"test": True},
        )

    def balance(self, user):
        return account_balance(
            ensure_wallet(user, "USD").ledger_account
        )

    def pending_balance(self):
        account = LedgerAccount.objects.get(
            name="WITHDRAWAL_PENDING",
            currency="USD",
        )
        return account_balance(account)

    def test_withdrawal_reserves_funds_once(self):
        before = self.balance(self.user)

        req, tx = create_withdrawal(
            self.user,
            Decimal("10.00"),
            currency="USD",
            method="bank",
            destination_reference="TEST-DESTINATION",
        )

        self.assertEqual(req.status, WithdrawalRequest.PENDING)
        self.assertEqual(req.amount, Decimal("10.00"))
        self.assertEqual(req.fee, Decimal("1.00"))

        self.assertEqual(
            self.balance(self.user),
            Decimal("9.00"),
        )

        self.assertEqual(
            self.pending_balance(),
            Decimal("10.00"),
        )

        self.assertEqual(
            before - Decimal("11.00"),
            self.balance(self.user),
        )

    def test_cannot_withdraw_more_than_available(self):
        with self.assertRaises(ValueError):
            create_withdrawal(
                self.user,
                Decimal("20.00"),
                currency="USD",
                method="bank",
                destination_reference="TEST-DESTINATION",
            )

        self.assertEqual(
            self.balance(self.user),
            Decimal("20.00"),
        )

    def test_complete_withdrawal_settles_once(self):
        req, _ = create_withdrawal(
            self.user,
            Decimal("10.00"),
            currency="USD",
            method="bank",
            destination_reference="TEST-DESTINATION",
        )

        complete_withdrawal(
            req.pk,
            provider_reference="TEST-PROVIDER-001",
        )

        req.refresh_from_db()

        self.assertEqual(
            req.status,
            WithdrawalRequest.COMPLETED,
        )

        pending_before = self.pending_balance()

        complete_withdrawal(
            req.pk,
            provider_reference="TEST-PROVIDER-002",
        )

        req.refresh_from_db()

        self.assertEqual(
            req.status,
            WithdrawalRequest.COMPLETED,
        )

        self.assertEqual(
            self.pending_balance(),
            pending_before,
        )

    def test_failed_withdrawal_returns_amount(self):
        req, _ = create_withdrawal(
            self.user,
            Decimal("10.00"),
            currency="USD",
            method="bank",
            destination_reference="TEST-DESTINATION",
        )

        self.assertEqual(
            self.balance(self.user),
            Decimal("9.00"),
        )

        fail_withdrawal(
            req.pk,
            reason="TEST_PROVIDER_FAILURE",
        )

        req.refresh_from_db()

        self.assertEqual(
            req.status,
            WithdrawalRequest.FAILED,
        )

        self.assertEqual(
            self.balance(self.user),
            Decimal("19.00"),
        )

        self.assertEqual(
            self.pending_balance(),
            Decimal("0.00"),
        )

    def test_completed_withdrawal_cannot_be_reversed(self):
        req, _ = create_withdrawal(
            self.user,
            Decimal("10.00"),
            currency="USD",
            method="bank",
            destination_reference="TEST-DESTINATION",
        )

        complete_withdrawal(
            req.pk,
            provider_reference="TEST-PROVIDER-001",
        )

        with self.assertRaises(ValueError):
            fail_withdrawal(
                req.pk,
                reason="ATTEMPTED_REVERSAL",
            )

        req.refresh_from_db()

        self.assertEqual(
            req.status,
            WithdrawalRequest.COMPLETED,
        )

    def test_other_user_has_no_access_to_withdrawal_request(self):
        req, _ = create_withdrawal(
            self.user,
            Decimal("10.00"),
            currency="USD",
            method="bank",
            destination_reference="TEST-DESTINATION",
        )

        self.assertNotEqual(
            req.user_id,
            self.attacker.id,
        )

        self.assertEqual(
            self.balance(self.attacker),
            Decimal("0.00"),
        )

        self.assertEqual(
            self.balance(self.user),
            Decimal("9.00"),
        )

    def test_concurrent_withdrawals_cannot_double_spend_wallet(self):
        from django.db import close_old_connections
        from threading import Barrier, Thread

        # Use a separate user with exactly enough money for ONE withdrawal.
        race_user = User.objects.create_user(
            username="withdrawal_race_user"
        )

        ensure_wallet(race_user, "USD")

        credit_cash(
            race_user,
            Decimal("20.00"),
            currency="USD",
            reference="RACE_TEST_DEPOSIT",
            metadata={"test": True},
        )

        barrier = Barrier(2)
        results = []

        def attempt():
            close_old_connections()
            try:
                barrier.wait(timeout=5)

                req, _ = create_withdrawal(
                    race_user,
                    Decimal("15.00"),
                    currency="USD",
                    method="bank",
                    destination_reference="RACE-TEST",
                )

                results.append(("success", req.pk))

            except Exception as exc:
                results.append(("failed", type(exc).__name__, str(exc)))

            finally:
                close_old_connections()

        t1 = Thread(target=attempt)
        t2 = Thread(target=attempt)

        t1.start()
        t2.start()

        t1.join(timeout=10)
        t2.join(timeout=10)

        self.assertFalse(t1.is_alive())
        self.assertFalse(t2.is_alive())

        successful = [
            result for result in results
            if result[0] == "success"
        ]

        self.assertLessEqual(
            len(successful),
            1,
            "Concurrent withdrawals double-spent the wallet.",
        )

        final_balance = self.balance(race_user)

        self.assertGreaterEqual(
            final_balance,
            Decimal("0.00"),
        )

        self.assertLessEqual(
            WithdrawalRequest.objects.filter(
                user=race_user
            ).count(),
            1,
        )

