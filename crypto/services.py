from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from .models import CryptoDeposit, CryptoWithdrawal
from finance.models import CryptoAssetConfig
from ledger.wallet_service import credit_cash, ensure_wallet
from ledger.models import LedgerAccount, LedgerEntry
from ledger.services import create_transaction, account_balance


def get_asset_config(asset):
    cfg = CryptoAssetConfig.objects.filter(asset=str(asset).upper(), enabled=True).first()
    if not cfg:
        raise ValueError("This crypto asset is currently disabled.")
    return cfg


@transaction.atomic
def record_deposit(*, user, asset, amount, address, tx_hash, network=""):
    cfg = get_asset_config(asset)
    amount = Decimal(str(amount))
    if amount <= 0 or amount < cfg.min_deposit:
        raise ValueError("Crypto deposit is below the configured minimum.")
    obj, created = CryptoDeposit.objects.get_or_create(
        tx_hash=tx_hash,
        defaults={"user": user, "asset": cfg.asset, "network": network or cfg.network, "amount": amount, "address": address},
    )
    if not created:
        if obj.user_id != user.id:
            raise ValueError("Transaction hash already belongs to another user.")
    return obj


@transaction.atomic
def confirm_deposit(*, deposit_id, fiat_amount, currency="USD", confirmations=None):
    deposit = CryptoDeposit.objects.select_for_update().get(pk=deposit_id)
    cfg = get_asset_config(deposit.asset)
    count = confirmations if confirmations is not None else cfg.confirmation_count
    if count < cfg.confirmation_count:
        raise ValueError("Required confirmations have not been reached.")
    if deposit.status == CryptoDeposit.CONFIRMED:
        return deposit
    fiat_amount = Decimal(str(fiat_amount))
    if fiat_amount <= 0:
        raise ValueError("Credit amount must be positive.")
    credit_cash(deposit.user, fiat_amount, currency, reference=f"CRYPTO_DEPOSIT:{deposit.tx_hash}",
                metadata={"crypto_deposit_id": deposit.pk, "asset": deposit.asset, "tx_hash": deposit.tx_hash})
    deposit.confirmations = count
    deposit.status = CryptoDeposit.CONFIRMED
    deposit.confirmed_at = timezone.now()
    deposit.save(update_fields=["confirmations", "status", "confirmed_at"])
    return deposit


@transaction.atomic
def create_withdrawal(*, user, asset, amount, destination_address, network=""):
    cfg = get_asset_config(asset)
    amount = Decimal(str(amount))
    if amount <= 0 or amount < cfg.min_withdrawal:
        raise ValueError("Crypto withdrawal is below the configured minimum.")
    fee = cfg.withdrawal_fee
    wallet = ensure_wallet(user, "USD").ledger_account
    available = account_balance(wallet)
    # Crypto conversion/payout is represented by a USD reservation until the provider settles it.
    if available < amount + fee:
        raise ValueError("Insufficient withdrawable balance.")
    pending, _ = LedgerAccount.objects.get_or_create(
        name="CRYPTO_WITHDRAWAL_PENDING", currency="USD",
        defaults={"account_type": LedgerAccount.LIABILITY},
    )
    revenue, _ = LedgerAccount.objects.get_or_create(
        name="FEE_REVENUE", currency="USD",
        defaults={"account_type": LedgerAccount.REVENUE},
    )
    postings = [
        {"account": wallet, "direction": LedgerEntry.DEBIT, "amount": amount + fee},
        {"account": pending, "direction": LedgerEntry.CREDIT, "amount": amount},
    ]
    if fee:
        postings.append({"account": revenue, "direction": LedgerEntry.CREDIT, "amount": fee})
    tx = create_transaction(description=f"Reserve crypto withdrawal for {user.username}",
                            reference=f"CRYPTO_WITHDRAWAL_RESERVE:{user.id}:{asset}:{amount}",
                            postings=postings,
                            metadata={"asset": cfg.asset, "network": network or cfg.network, "fee": str(fee)})
    req = CryptoWithdrawal.objects.create(user=user, asset=cfg.asset, network=network or cfg.network,
                                          amount=amount, fee=fee, destination_address=destination_address)
    return req, tx
