from uuid import uuid4
from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from .models import BankTransfer
from finance.models import FinanceSettings
from ledger.wallet_service import credit_cash


@transaction.atomic
def create_deposit(*, user, amount, currency="USD"):
    amount = Decimal(str(amount))
    settings = FinanceSettings.get_solo()
    if not settings.bank_transfer_enabled:
        raise ValueError("Bank transfer deposits are currently disabled.")
    if amount < settings.min_deposit:
        raise ValueError("Deposit is below the configured minimum.")
    if settings.max_deposit is not None and amount > settings.max_deposit:
        raise ValueError("Deposit exceeds the configured maximum.")
    reference = "BT-" + uuid4().hex.upper()
    return BankTransfer.objects.create(user=user, amount=amount, currency=currency.upper(), reference=reference)


@transaction.atomic
def confirm_deposit(*, transfer_id, provider_reference=""):
    transfer = BankTransfer.objects.select_for_update().get(pk=transfer_id)
    if transfer.status == BankTransfer.CONFIRMED:
        return transfer
    if transfer.status != BankTransfer.PENDING:
        raise ValueError("Only pending bank transfers can be confirmed.")
    credit_cash(transfer.user, transfer.amount, transfer.currency,
                reference=f"BANK_TRANSFER:{transfer.reference}",
                metadata={"bank_transfer_id": transfer.pk, "provider_reference": provider_reference})
    transfer.status = BankTransfer.CONFIRMED
    transfer.provider_reference = provider_reference
    transfer.confirmed_at = timezone.now()
    transfer.save(update_fields=["status", "provider_reference", "confirmed_at"])
    return transfer


@transaction.atomic
def fail_transfer(transfer_id, reason=""):
    transfer = BankTransfer.objects.select_for_update().get(pk=transfer_id)
    if transfer.status != BankTransfer.PENDING:
        raise ValueError("Only pending bank transfers can be failed.")
    transfer.status = BankTransfer.FAILED
    transfer.provider_reference = reason[:160]
    transfer.save(update_fields=["status", "provider_reference"])
    return transfer
