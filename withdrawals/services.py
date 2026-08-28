from decimal import Decimal
from django.db import transaction

from ledger.wallet_service import ensure_wallet
from ledger.models import LedgerAccount, LedgerEntry
from ledger.services import create_transaction, account_balance
from finance.models import FinanceSettings, PayoutProviderConfig

from .models import WithdrawalRequest


@transaction.atomic
def create_withdrawal(
    user,
    amount,
    currency="USD",
    method="bank",
    destination_reference="",
    provider="",
    provider_recipient="",
    provider_metadata=None,
):
    amount = Decimal(str(amount))
    currency = str(currency).upper().strip()
    provider = str(provider or "").lower().strip()

    fs = FinanceSettings.get_solo()

    if amount <= 0:
        raise ValueError("Withdrawal amount must be positive.")
    if amount < fs.min_withdrawal:
        raise ValueError("Below minimum withdrawal.")
    if fs.max_withdrawal is not None and amount > fs.max_withdrawal:
        raise ValueError("Above maximum withdrawal.")

    if provider:
        config = (
            PayoutProviderConfig.objects
            .filter(provider=provider, enabled=True)
            .first()
        )

        if not config:
            raise ValueError(
                f"Payout provider '{provider}' is not enabled."
            )

        currencies = {
            str(c).upper().strip()
            for c in (config.supported_currencies or [])
            if str(c).strip()
        }

        if currencies and currency not in currencies:
            raise ValueError(
                f"Payout provider '{provider}' does not support {currency}."
            )

        countries = {
            str(c).upper().strip()
            for c in (config.supported_countries or [])
            if str(c).strip()
        }

        if countries:
            profile = getattr(user, "profile", None)
            user_country = str(
                getattr(profile, "country", "") or ""
            ).strip()

            if not user_country:
                raise ValueError(
                    "Your country must be set before using this payout provider."
                )

            normalized_country = user_country.upper()

            country_names = {
                "UNITED STATES": "US",
                "UNITED STATES OF AMERICA": "US",
                "CANADA": "CA",
                "UNITED KINGDOM": "GB",
                "NIGERIA": "NG",
                "GHANA": "GH",
                "KENYA": "KE",
                "SOUTH AFRICA": "ZA",
                "ALGERIA": "DZ",
                "FRANCE": "FR",
                "GERMANY": "DE",
                "ITALY": "IT",
                "SPAIN": "ES",
                "TURKEY": "TR",
                "UNITED ARAB EMIRATES": "AE",
                "INDIA": "IN",
                "AUSTRALIA": "AU",
                "NEW ZEALAND": "NZ",
                "JAPAN": "JP",
                "CHINA": "CN",
                "SINGAPORE": "SG",
            }

            normalized_country = country_names.get(
                normalized_country,
                normalized_country,
            )

            if normalized_country not in countries:
                raise ValueError(
                    f"Payout provider '{provider}' does not support payouts "
                    f"to your country."
                )

        if amount < config.min_amount:
            raise ValueError(
                f"Withdrawal is below the minimum amount for {provider}."
            )

        if (
            config.max_amount is not None
            and amount > config.max_amount
        ):
            raise ValueError(
                f"Withdrawal exceeds the maximum amount for {provider}."
            )

    fee = Decimal(str(fs.withdrawal_fee))
    cash = ensure_wallet(user, currency).ledger_account
    cash = LedgerAccount.objects.select_for_update().get(pk=cash.pk)

    if account_balance(cash) < amount + fee:
        raise ValueError("Insufficient withdrawable cash balance.")

    pending, _ = LedgerAccount.objects.get_or_create(
        name="WITHDRAWAL_PENDING",
        currency=currency,
        defaults={"account_type": LedgerAccount.LIABILITY},
    )
    revenue, _ = LedgerAccount.objects.get_or_create(
        name="FEE_REVENUE",
        currency=currency,
        defaults={"account_type": LedgerAccount.REVENUE},
    )

    postings = [
        {"account": cash, "direction": LedgerEntry.DEBIT, "amount": amount + fee},
        {"account": pending, "direction": LedgerEntry.CREDIT, "amount": amount},
    ]

    if fee:
        postings.append({
            "account": revenue,
            "direction": LedgerEntry.CREDIT,
            "amount": fee,
        })

    tx = create_transaction(
        description=f"Reserve withdrawal for {user.username}",
        reference=f"WITHDRAWAL_RESERVE:{user.id}:{currency}:{amount}:{provider or 'manual'}",
        postings=postings,
        metadata={
            "user_id": user.id,
            "withdrawal": True,
            "fee": str(fee),
            "method": method,
            "provider": provider,
            "currency": currency,
        },
    )

    req = WithdrawalRequest.objects.create(
        user=user,
        amount=amount,
        fee=fee,
        currency=currency,
        method=method,
        provider=provider,
        destination_reference=destination_reference,
        provider_recipient=provider_recipient,
        provider_metadata=provider_metadata or {},
    )

    return req, tx


@transaction.atomic
def mark_withdrawal_processing(
    request_id,
    provider_reference="",
    provider_recipient="",
    metadata=None,
):
    req = WithdrawalRequest.objects.select_for_update().get(pk=request_id)

    if req.status == WithdrawalRequest.COMPLETED:
        return req

    if req.status not in (
        WithdrawalRequest.PENDING,
        WithdrawalRequest.PROCESSING,
    ):
        raise ValueError("Withdrawal cannot be moved to processing.")

    if (
        req.status == WithdrawalRequest.PROCESSING
        and req.provider_reference
        and provider_reference
        and req.provider_reference != provider_reference
    ):
        raise ValueError(
            "Withdrawal is already processing with a different provider reference."
        )

    req.status = WithdrawalRequest.PROCESSING

    if provider_reference:
        req.provider_reference = provider_reference
    if provider_recipient:
        req.provider_recipient = provider_recipient
    if metadata:
        req.provider_metadata = {
            **(req.provider_metadata or {}),
            **metadata,
        }

    req.save(update_fields=[
        "status",
        "provider_reference",
        "provider_recipient",
        "provider_metadata",
        "updated_at",
    ])
    return req


@transaction.atomic
def complete_withdrawal(request_id, provider_reference="",
                        metadata=None):
    req = WithdrawalRequest.objects.select_for_update().get(pk=request_id)

    if req.status == WithdrawalRequest.COMPLETED:
        return req

    if req.status not in (
        WithdrawalRequest.PENDING,
        WithdrawalRequest.PROCESSING,
    ):
        raise ValueError("Withdrawal cannot be completed from its current status.")

    pending = LedgerAccount.objects.get(
        name="WITHDRAWAL_PENDING",
        currency=req.currency,
    )
    settlement, _ = LedgerAccount.objects.get_or_create(
        name="PAYOUT_CLEARING",
        currency=req.currency,
        defaults={"account_type": LedgerAccount.ASSET},
    )

    create_transaction(
        description=f"Complete withdrawal #{req.pk}",
        reference=f"WITHDRAWAL_COMPLETE:{req.pk}",
        idempotency_key=f"WITHDRAWAL_COMPLETE:{req.pk}",
        postings=[
            {"account": pending, "direction": LedgerEntry.DEBIT, "amount": req.amount},
            {"account": settlement, "direction": LedgerEntry.CREDIT, "amount": req.amount},
        ],
        metadata={
            "withdrawal_id": req.pk,
            "provider": req.provider,
            "provider_reference": provider_reference,
        },
    )

    req.status = WithdrawalRequest.COMPLETED
    if provider_reference:
        req.provider_reference = provider_reference
    if metadata:
        req.provider_metadata = {
            **(req.provider_metadata or {}),
            **metadata,
        }

    req.save(update_fields=[
        "status",
        "provider_reference",
        "provider_metadata",
        "updated_at",
    ])
    return req


@transaction.atomic
def fail_withdrawal(request_id, reason="", metadata=None):
    req = WithdrawalRequest.objects.select_for_update().get(pk=request_id)

    if req.status in (
        WithdrawalRequest.FAILED,
        WithdrawalRequest.CANCELLED,
    ):
        return req

    if req.status == WithdrawalRequest.COMPLETED:
        raise ValueError("Completed withdrawal cannot be reversed here.")

    pending = LedgerAccount.objects.get(
        name="WITHDRAWAL_PENDING",
        currency=req.currency,
    )
    cash = ensure_wallet(req.user, req.currency).ledger_account

    create_transaction(
        description=f"Return failed withdrawal #{req.pk}",
        reference=f"WITHDRAWAL_RETURN:{req.pk}",
        idempotency_key=f"WITHDRAWAL_RETURN:{req.pk}",
        postings=[
            {"account": pending, "direction": LedgerEntry.DEBIT, "amount": req.amount},
            {"account": cash, "direction": LedgerEntry.CREDIT, "amount": req.amount},
        ],
        metadata={
            "withdrawal_id": req.pk,
            "failure_reason": reason,
            "provider": req.provider,
        },
    )

    req.status = WithdrawalRequest.FAILED
    req.failure_reason = reason

    if metadata:
        req.provider_metadata = {
            **(req.provider_metadata or {}),
            **metadata,
        }

    req.save(update_fields=[
        "status",
        "failure_reason",
        "provider_metadata",
        "updated_at",
    ])
    return req
