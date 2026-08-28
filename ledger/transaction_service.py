from decimal import Decimal
from django.db import transaction
from .models import LedgerAccount, LedgerEntry
from .services import create_transaction, account_balance
from .wallet_service import ensure_wallet, gift_balance, credit_cash


def wallet_balance(user, currency="USD"):
    return account_balance(ensure_wallet(user, currency).ledger_account)


def test_deposit(user, amount, currency="USD"):
    return credit_cash(
        user,
        amount,
        currency=currency,
        reference=f"TEST_DEPOSIT:{user.id}",
        metadata={
            "test": True,
            "source": "test_deposit_api",
        },
    )

@transaction.atomic
def purchase_order(order):
    from escrow.models import Escrow
    from marketplace.models import Order

    # Lock the database row so two concurrent purchase requests cannot
    # both transition the same pending order into escrow.
    #
    # Keep the caller's original model instance so callers/tests that
    # already hold this object see the status mutation as well.
    Order.objects.select_for_update().get(pk=order.pk)
    order.refresh_from_db()

    if order.status != "pending":
        raise ValueError(
            f"Order cannot be purchased from status {order.status}"
        )

    amount = Decimal(str(order.amount))

    # Resolve the buyer cash account, then lock the ledger account
    # before reading its balance.
    cash = ensure_wallet(
        order.buyer,
        order.currency,
    ).ledger_account

    cash = LedgerAccount.objects.select_for_update().get(
        pk=cash.pk
    )

    # Resolve the gift balance account, then lock it before reading
    # its balance.
    gift, _ = LedgerAccount.objects.get_or_create(
        name=f"GIFT_BALANCE:{order.buyer_id}",
        currency=order.currency,
        defaults={
            "account_type": LedgerAccount.LIABILITY,
        },
    )

    gift = LedgerAccount.objects.select_for_update().get(
        pk=gift.pk
    )

    # Lock the escrow account as well.
    escrow_account, _ = LedgerAccount.objects.get_or_create(
        name="ESCROW",
        currency=order.currency,
        defaults={
            "account_type": LedgerAccount.LIABILITY,
            "active": True,
        },
    )

    escrow_account = LedgerAccount.objects.select_for_update().get(
        pk=escrow_account.pk
    )

    # These reads now occur while the relevant PostgreSQL rows are locked.
    cash_available = account_balance(cash)
    gift_available = account_balance(gift)
    if cash_available + gift_available < amount:
        raise ValueError(f"Insufficient funds: cash={cash_available}, gift={gift_available}, required={amount}")
    gift_used = min(gift_available, amount)
    cash_used = amount - gift_used
    postings = []
    if cash_used:
        postings += [{"account": cash, "direction": LedgerEntry.DEBIT, "amount": cash_used}]
    if gift_used:
        postings += [{"account": gift, "direction": LedgerEntry.DEBIT, "amount": gift_used}]
    postings.append({"account": escrow_account, "direction": LedgerEntry.CREDIT, "amount": amount})
    tx = create_transaction(
        description=f"Fund order #{order.id}", reference=f"ORDER_ESCROW:{order.id}", postings=postings,
        metadata={"order_id": order.id, "buyer_id": order.buyer_id, "cash_used": str(cash_used), "gift_used": str(gift_used), "gift_non_withdrawable": bool(gift_used)},
    )
    Escrow.objects.create(order=order, amount=amount, currency=order.currency, status=Escrow.HOLDING, funding_transaction_id=tx.transaction_id, funded_cash_amount=cash_used, funded_gift_amount=gift_used)
    order.status = order.ESCROW; order.save(update_fields=["status"])
    return tx
