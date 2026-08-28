from decimal import Decimal
import time
from uuid import uuid4

from django.db import IntegrityError, OperationalError, transaction
from django.db.models import Sum

from .models import LedgerAccount, LedgerEntry, LedgerTransaction


ZERO = Decimal("0")


@transaction.atomic
def _create_transaction(
    description,
    postings,
    reference="",
    metadata=None,
    idempotency_key=None,
):
    """
    postings:
        [
            {
                "account": LedgerAccount,
                "direction": "debit" or "credit",
                "amount": Decimal(...)
            },
            ...
        ]

    A transaction must balance:
        total debits == total credits
    """

    if not postings:
        raise ValueError("A transaction needs postings")

    if idempotency_key:
        existing = LedgerTransaction.objects.filter(
            idempotency_key=str(idempotency_key)
        ).first()
        if existing:
            return existing

    debit = sum(
        (Decimal(str(x["amount"])) for x in postings
         if x["direction"] == LedgerEntry.DEBIT),
        ZERO,
    )

    credit = sum(
        (Decimal(str(x["amount"])) for x in postings
         if x["direction"] == LedgerEntry.CREDIT),
        ZERO,
    )

    if debit <= ZERO:
        raise ValueError("Transaction amount must be positive")

    if debit != credit:
        raise ValueError(
            f"Unbalanced transaction: debit={debit}, credit={credit}"
        )

    currencies = {
        x["account"].currency
        for x in postings
    }

    if len(currencies) != 1:
        raise ValueError(
            "All postings in a transaction must use one currency"
        )

    if idempotency_key:
        try:
            with transaction.atomic():
                tx = LedgerTransaction.objects.create(
                    transaction_id=uuid4().hex,
                    description=description,
                    reference=reference,
                    idempotency_key=str(idempotency_key),
                    metadata=metadata or {},
                )
        except IntegrityError:
            # Another concurrent request already created this transaction.
            # Its entries belong to that transaction, so DO NOT create
            # another set of entries here.
            return LedgerTransaction.objects.get(
                idempotency_key=str(idempotency_key)
            )
    else:
        tx = LedgerTransaction.objects.create(
            transaction_id=uuid4().hex,
            description=description,
            reference=reference,
            metadata=metadata or {},
        )

    LedgerEntry.objects.bulk_create([
        LedgerEntry(
            transaction=tx,
            account=x["account"],
            amount=Decimal(str(x["amount"])),
            direction=x["direction"],
        )
        for x in postings
    ])

    return tx



def create_transaction(
    description,
    postings,
    reference="",
    metadata=None,
    idempotency_key=None,
):
    """
    Create a ledger transaction with retry handling for transient
    database-lock errors.

    SQLite can briefly lock a table when concurrent tests execute the
    same idempotent transaction. PostgreSQL handles this much better,
    but retrying transient lock errors also makes local development
    tests reliable.

    The retry surrounds the entire atomic operation so a failed
    transaction is completely rolled back before retrying.
    """
    max_attempts = 5

    for attempt in range(max_attempts):
        try:
            return _create_transaction(
                description=description,
                postings=postings,
                reference=reference,
                metadata=metadata,
                idempotency_key=idempotency_key,
            )
        except OperationalError as exc:
            message = str(exc).lower()

            if (
                "database is locked" not in message
                and "database table is locked" not in message
            ):
                raise

            if attempt == max_attempts - 1:
                raise

            # Give the competing transaction time to commit.
            time.sleep(0.05 * (attempt + 1))


def account_balance(account):
    """
    Returns the signed balance of an account.

    Asset/expense:
        debit increases balance

    Liability/revenue/equity:
        credit increases balance
    """

    debit = LedgerEntry.objects.filter(
        account=account,
        direction=LedgerEntry.DEBIT,
    ).aggregate(
        total=Sum("amount")
    )["total"] or ZERO

    credit = LedgerEntry.objects.filter(
        account=account,
        direction=LedgerEntry.CREDIT,
    ).aggregate(
        total=Sum("amount")
    )["total"] or ZERO

    if account.account_type in (
        LedgerAccount.ASSET,
        LedgerAccount.EXPENSE,
    ):
        return debit - credit

    return credit - debit
