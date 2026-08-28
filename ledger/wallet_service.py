from decimal import Decimal
from django.db import transaction
from .models import LedgerAccount, LedgerEntry
from .wallet_models import Wallet
from .services import create_transaction, account_balance

CASH_PREFIX = "BUYER:"
GIFT_PREFIX = "GIFT_BALANCE:"

@transaction.atomic
def ensure_wallet(user, currency="USD"):
    # Seller wallets must use SELLER:<user_id>; buyer wallets use BUYER:<user_id>.
    from accounts.models import Profile

    profile, _ = Profile.objects.get_or_create(user=user)

    if profile.role == Profile.SELLER:
        account_name = f"SELLER:{user.id}"
    else:
        account_name = f"BUYER:{user.id}"

    account, _ = LedgerAccount.objects.get_or_create(
        name=account_name,
        currency=currency,
        defaults={"account_type": LedgerAccount.LIABILITY},
    )

    wallet, _ = Wallet.objects.get_or_create(
        user=user,
        currency=currency,
        defaults={"ledger_account": account},
    )
    if wallet.ledger_account_id != account.id:
        wallet.ledger_account = account
        wallet.save(update_fields=["ledger_account"])
    return wallet

def _gift_account(user, currency):
    account, _ = LedgerAccount.objects.get_or_create(
        name=f"{GIFT_PREFIX}{user.id}", currency=currency,
        defaults={"account_type": LedgerAccount.LIABILITY},
    )
    return account

def wallet_balance(user, currency="USD"):
    return account_balance(ensure_wallet(user, currency).ledger_account)

def gift_balance(user, currency="USD"):
    return account_balance(_gift_account(user, currency))

@transaction.atomic
def credit_cash(user, amount, currency="USD", reference="", metadata=None):
    amount = Decimal(str(amount))
    if amount <= 0: raise ValueError("Amount must be greater than zero")
    buyer = ensure_wallet(user, currency).ledger_account
    clearing, _ = LedgerAccount.objects.get_or_create(
        name="PAYMENT_CLEARING", currency=currency,
        defaults={"account_type": LedgerAccount.ASSET},
    )
    return create_transaction(
        description=f"Cash wallet credit for {user.username}", reference=reference,
        postings=[
            {"account": clearing, "direction": LedgerEntry.DEBIT, "amount": amount},
            {"account": buyer, "direction": LedgerEntry.CREDIT, "amount": amount},
        ], metadata=metadata or {},
    )

@transaction.atomic
def credit_gift_balance(user, amount, currency="USD", reference="", metadata=None):
    amount = Decimal(str(amount))
    if amount <= 0: raise ValueError("Amount must be greater than zero")
    gift = _gift_account(user, currency)
    liability, _ = LedgerAccount.objects.get_or_create(
        name="GIFT_CARD_LIABILITY", currency=currency,
        defaults={"account_type": LedgerAccount.LIABILITY},
    )
    return create_transaction(
        description=f"Gift-card wallet credit for {user.username}", reference=reference,
        postings=[
            {"account": liability, "direction": LedgerEntry.DEBIT, "amount": amount},
            {"account": gift, "direction": LedgerEntry.CREDIT, "amount": amount},
        ], metadata={**(metadata or {}), "non_withdrawable": True},
    )
