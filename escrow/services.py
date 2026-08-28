from decimal import Decimal
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from audit.models import AuditEvent
from ledger.models import LedgerAccount, LedgerEntry
from ledger.services import create_transaction, account_balance
from .models import Escrow


def _escrow_accounts(escrow):
    order = escrow.order
    escrow_account = LedgerAccount.objects.select_for_update().get(
        name="ESCROW", currency=escrow.currency
    )
    seller_account, _ = LedgerAccount.objects.get_or_create(
        name=f"SELLER:{order.product.seller_id}",
        currency=escrow.currency,
        defaults={"account_type": LedgerAccount.LIABILITY},
    )
    seller_account = LedgerAccount.objects.select_for_update().get(
        pk=seller_account.pk
    )
    buyer_account = LedgerAccount.objects.select_for_update().get(
        name=f"BUYER:{order.buyer_id}", currency=escrow.currency
    )
    return escrow_account, seller_account, buyer_account


def _require_operator(actor):
    """
    Administrative settlement requires an explicit authorized actor.

    actor=None is NEVER accepted here. Trusted automation must use the
    dedicated internal settlement path instead of bypassing authorization.
    """
    if actor is None:
        raise PermissionError("Explicit actor required.")
    if not actor.has_perm("escrow.settle_escrow"):
        raise PermissionError("You are not authorized to settle this escrow.")


@transaction.atomic
def _release_escrow_internal(escrow, *, actor=None, reason="system"):
    """
    Internal settlement primitive.

    This must only be called after the caller has already established
    authorization. It does not perform user authorization itself.
    """
    if escrow.status != Escrow.HOLDING:
        raise ValueError("Escrow is not releasable")

    amount = Decimal(str(escrow.amount))
    escrow_account, seller_account, _ = _escrow_accounts(escrow)

    tx = create_transaction(
        description=f"Release escrow #{escrow.pk}",
        reference=f"ESCROW_RELEASE:{escrow.pk}",
        idempotency_key=f"escrow-release:{escrow.pk}",
        postings=[
            {
                "account": escrow_account,
                "direction": LedgerEntry.DEBIT,
                "amount": amount,
            },
            {
                "account": seller_account,
                "direction": LedgerEntry.CREDIT,
                "amount": amount,
            },
        ],
        metadata={
            "escrow_id": escrow.pk,
            "order_id": escrow.order_id,
            "operation": "release",
            "reason": reason,
        },
    )

    escrow.status = Escrow.RELEASED
    escrow.released_at = timezone.now()
    escrow.save(update_fields=["status", "released_at"])

    order = escrow.order
    order.status = order.COMPLETED
    order.confirmed_at = timezone.now()
    order.save(update_fields=["status", "confirmed_at"])

    from referrals.services import award_referral_commission
    referral_tx = award_referral_commission(order.id)

    AuditEvent.objects.create(
        actor=actor,
        action="escrow.released",
        object_type="Escrow",
        object_id=str(escrow.pk),
        metadata={
            "order_id": order.id,
            "amount": str(amount),
            "currency": escrow.currency,
            "transaction_id": tx.transaction_id,
            "referral_transaction_id": (
                referral_tx.transaction_id if referral_tx else None
            ),
            "reason": reason,
        },
    )

    return tx


@transaction.atomic
def release_escrow(escrow_id, actor=None, reason="manual"):
    """
    Administrative settlement entry point.

    An explicit authorized actor is required.
    """
    escrow = (
        Escrow.objects.select_for_update()
        .select_related("order", "order__product")
        .get(pk=escrow_id)
    )

    _require_operator(actor)

    was_disputed = escrow.status == Escrow.DISPUTED
    tx = _release_escrow_internal(
        escrow,
        actor=actor,
        reason=reason,
    )
    if was_disputed:
        from stage4.models import DisputeEvent
        DisputeEvent.objects.create(
            order=escrow.order,
            actor=actor,
            event_type="resolved",
            message="Dispute resolved in seller's favor.",
            metadata={"outcome": "seller_favor", "resolution": "release"},
        )
    return tx


@transaction.atomic
def settle_escrow_for_buyer(escrow_id, *, buyer, reason="buyer_confirmed"):
    """Buyer confirmation path; never grants the administrative settle permission."""
    escrow = (
        Escrow.objects.select_for_update()
        .select_related("order", "order__product")
        .get(pk=escrow_id)
    )
    if escrow.order.buyer_id != buyer.id:
        raise PermissionError("Only the buyer can confirm this order.")
    if escrow.status != Escrow.HOLDING:
        raise ValueError("Escrow is not releasable.")
    if escrow.order.status != escrow.order.DELIVERED:
        raise ValueError("Order must be delivered before confirmation.")
    if (
        escrow.order.confirmation_deadline
        and timezone.now() > escrow.order.confirmation_deadline
    ):
        raise ValueError("The confirmation window has expired.")

    # Buyer authorization has already been verified above.
    return _release_escrow_internal(
        escrow,
        actor=buyer,
        reason=reason,
    )


@transaction.atomic
def refund_escrow(escrow_id, actor=None, reason="manual"):
    escrow = (
        Escrow.objects.select_for_update()
        .select_related("order", "order__product")
        .get(pk=escrow_id)
    )
    if escrow.status != Escrow.HOLDING and escrow.status != Escrow.DISPUTED:
        raise ValueError("Escrow is not refundable")
    _require_operator(actor)

    was_disputed = escrow.status == Escrow.DISPUTED
    amount = Decimal(str(escrow.amount))
    escrow_account, _, buyer_account = _escrow_accounts(escrow)
    gift = LedgerAccount.objects.get_or_create(
        name=f"GIFT_BALANCE:{escrow.order.buyer_id}",
        currency=escrow.currency,
        defaults={"account_type": LedgerAccount.LIABILITY},
    )[0]

    cash_amount = Decimal(str(escrow.funded_cash_amount))
    gift_amount = Decimal(str(escrow.funded_gift_amount))
    if cash_amount + gift_amount != amount:
        raise ValueError("Escrow funding split is invalid")

    postings = [
        {"account": escrow_account, "direction": LedgerEntry.DEBIT, "amount": amount}
    ]
    if cash_amount:
        postings.append(
            {"account": buyer_account, "direction": LedgerEntry.CREDIT, "amount": cash_amount}
        )
    if gift_amount:
        postings.append(
            {"account": gift, "direction": LedgerEntry.CREDIT, "amount": gift_amount}
        )

    tx = create_transaction(
        description=f"Refund escrow #{escrow.pk}",
        reference=f"ESCROW_REFUND:{escrow.pk}",
        idempotency_key=f"escrow-refund:{escrow.pk}",
        postings=postings,
        metadata={
            "escrow_id": escrow.pk,
            "order_id": escrow.order_id,
            "operation": "refund",
            "reason": reason,
            "cash_refund": str(cash_amount),
            "gift_refund": str(gift_amount),
        },
    )
    escrow.status = Escrow.REFUNDED
    escrow.save(update_fields=["status"])
    escrow.order.status = escrow.order.REFUNDED
    escrow.order.save(update_fields=["status"])

    AuditEvent.objects.create(
        actor=actor,
        action="escrow.refunded",
        object_type="Escrow",
        object_id=str(escrow.pk),
        metadata={
            "order_id": escrow.order_id,
            "amount": str(amount),
            "currency": escrow.currency,
            "transaction_id": tx.transaction_id,
            "reason": reason,
        },
    )
    if was_disputed:
        from stage4.models import DisputeEvent
        DisputeEvent.objects.create(
            order=escrow.order,
            actor=actor,
            event_type="resolved",
            message="Dispute resolved in buyer's favor.",
            metadata={"outcome": "buyer_favor", "resolution": "refund"},
        )
    return tx


@transaction.atomic
def fund_private_escrow(escrow_id, buyer):
    from .models import PrivateEscrow

    e = (
        PrivateEscrow.objects.select_for_update()
        .select_related("seller", "buyer")
        .get(escrow_id=escrow_id)
    )
    if e.status != PrivateEscrow.CREATED:
        raise ValueError("Escrow is not awaiting funding")
    if e.buyer_id != buyer.id:
        raise ValueError("Only the invited buyer can fund this escrow")

    amount = Decimal(str(e.amount))
    buyer_account = LedgerAccount.objects.select_for_update().get(
        name=f"BUYER:{buyer.id}", currency=e.currency
    )
    escrow_account = LedgerAccount.objects.select_for_update().get(
        name="ESCROW", currency=e.currency
    )
    if account_balance(buyer_account) < amount:
        raise ValueError("Insufficient funds")

    tx = create_transaction(
        description=f"Fund private escrow {e.escrow_id}",
        reference=f"PRIVATE_ESCROW_FUND:{e.escrow_id}",
        postings=[
            {"account": buyer_account, "direction": LedgerEntry.DEBIT, "amount": amount},
            {"account": escrow_account, "direction": LedgerEntry.CREDIT, "amount": amount},
        ],
        metadata={"private_escrow_id": e.escrow_id, "buyer_id": buyer.id},
    )
    e.status = PrivateEscrow.FUNDED
    e.funded_at = timezone.now()
    hours = getattr(
        settings,
        "SHOPU_AUTO_RELEASE_HOURS",
        6,
    )
    try:
        from finance.models import FinanceSettings
        hours = FinanceSettings.get_solo().escrow_auto_release_hours
    except Exception:
        pass
    e.deadline = timezone.now() + timedelta(hours=hours)
    e.funded_cash_amount = amount
    e.funding_transaction_id = tx.transaction_id
    e.save(
        update_fields=[
            "status",
            "funded_at",
            "deadline",
            "funded_cash_amount",
            "funding_transaction_id",
        ]
    )
    return tx


@transaction.atomic
def _release_private_escrow_internal(escrow, *, actor=None, reason="system"):
    """
    Internal private-escrow settlement primitive.

    Authorization must already have been established by the caller.
    Trusted automation uses this function directly.
    """
    from .models import PrivateEscrow

    if escrow.status != PrivateEscrow.DELIVERED:
        raise ValueError("Private escrow must be delivered before release.")

    amount = Decimal(str(escrow.amount))

    escrow_account = LedgerAccount.objects.select_for_update().get(
        name="ESCROW",
        currency=escrow.currency,
    )

    seller_account, _ = LedgerAccount.objects.get_or_create(
        name=f"SELLER:{escrow.seller_id}",
        currency=escrow.currency,
        defaults={"account_type": LedgerAccount.LIABILITY},
    )

    seller_account = LedgerAccount.objects.select_for_update().get(
        pk=seller_account.pk
    )

    tx = create_transaction(
        description=f"Release private escrow {escrow.escrow_id}",
        reference=f"PRIVATE_ESCROW_RELEASE:{escrow.escrow_id}",
        idempotency_key=f"private-escrow-release:{escrow.escrow_id}",
        postings=[
            {
                "account": escrow_account,
                "direction": LedgerEntry.DEBIT,
                "amount": amount,
            },
            {
                "account": seller_account,
                "direction": LedgerEntry.CREDIT,
                "amount": amount,
            },
        ],
        metadata={
            "private_escrow_id": escrow.escrow_id,
            "operation": "release",
            "reason": reason,
        },
    )

    escrow.status = PrivateEscrow.RELEASED
    escrow.released_at = timezone.now()
    escrow.save(update_fields=["status", "released_at"])

    return tx


@transaction.atomic
def release_private_escrow(escrow_id, actor=None, reason="buyer_confirmed"):
    """
    Public private-escrow settlement path.

    Buyer may release their own delivered escrow.
    Authorized operators may also release it.
    Automation must use _release_private_escrow_internal().
    """
    from .models import PrivateEscrow

    escrow = (
        PrivateEscrow.objects.select_for_update()
        .select_related("seller", "buyer")
        .get(escrow_id=escrow_id)
    )

    if escrow.status != PrivateEscrow.DELIVERED:
        raise ValueError("Private escrow must be delivered before release.")

    if actor is None:
        raise PermissionError("Explicit actor required.")

    if (
        actor.id != escrow.buyer_id
        and not actor.has_perm("escrow.settle_escrow")
    ):
        raise PermissionError(
            "You are not authorized to release this escrow."
        )

    return _release_private_escrow_internal(
        escrow,
        actor=actor,
        reason=reason,
    )
