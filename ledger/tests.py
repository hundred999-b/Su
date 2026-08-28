from decimal import Decimal
from threading import Barrier, Thread

from django.db import connections
from django.test import TransactionTestCase

from .models import LedgerAccount, LedgerEntry, LedgerTransaction
from .services import create_transaction


class LedgerIdempotencyConcurrencyTests(TransactionTestCase):
    reset_sequences = True

    def test_concurrent_same_idempotency_key_creates_one_transaction(self):
        account_a = LedgerAccount.objects.create(
            name="RACE_ASSET",
            account_type=LedgerAccount.ASSET,
            currency="USD",
        )

        account_b = LedgerAccount.objects.create(
            name="RACE_LIABILITY",
            account_type=LedgerAccount.LIABILITY,
            currency="USD",
        )

        barrier = Barrier(2)
        results = []

        def attempt():
            try:
                # Force this worker thread to start with a clean
                # thread-local Django database connection state.
                connections.close_all()

                barrier.wait(timeout=10)

                tx = create_transaction(
                    description="Concurrent idempotency test",
                    reference="RACE_IDEMPOTENCY",
                    idempotency_key="race-ledger-key",
                    postings=[
                        {
                            "account": account_a,
                            "direction": LedgerEntry.DEBIT,
                            "amount": Decimal("10.00"),
                        },
                        {
                            "account": account_b,
                            "direction": LedgerEntry.CREDIT,
                            "amount": Decimal("10.00"),
                        },
                    ],
                )

                results.append(("success", tx.transaction_id))

            except Exception as exc:
                results.append(
                    ("error", type(exc).__name__, str(exc))
                )

            finally:
                # Close EVERY Django database connection belonging
                # to this worker thread.
                connections.close_all()

        t1 = Thread(target=attempt, name="ledger-race-1")
        t2 = Thread(target=attempt, name="ledger-race-2")

        t1.start()
        t2.start()

        t1.join(timeout=15)
        t2.join(timeout=15)

        # Make absolutely sure the worker threads are gone before
        # Django starts destroying the test database.
        self.assertFalse(t1.is_alive())
        self.assertFalse(t2.is_alive())

        # Close any connection associated with the main test thread.
        connections.close_all()

        successful = [
            result
            for result in results
            if result[0] == "success"
        ]

        self.assertEqual(
            len(successful),
            2,
            f"Concurrent calls did not both resolve successfully: {results}",
        )

        transaction_ids = {
            result[1]
            for result in successful
        }

        self.assertEqual(
            len(transaction_ids),
            1,
            f"Concurrent calls created different transactions: {results}",
        )

        self.assertEqual(
            LedgerTransaction.objects.filter(
                idempotency_key="race-ledger-key"
            ).count(),
            1,
        )

        self.assertEqual(
            LedgerEntry.objects.filter(
                transaction__idempotency_key="race-ledger-key"
            ).count(),
            2,
        )
