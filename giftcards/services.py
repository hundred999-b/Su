from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from .models import GiftCard, GiftCardRedemption, GiftCardPurchase, GiftCardTopUp, GiftCardTopUpSettings
from ledger.wallet_service import credit_gift_balance

@transaction.atomic
def redeem_gift_card(code, user):
    card = GiftCard.objects.select_for_update().get(code=code.strip().upper())
    if card.status != GiftCard.ACTIVE: raise ValueError("Gift card is not active")
    if card.expires_at and card.expires_at <= timezone.now():
        card.status = GiftCard.EXPIRED; card.save(update_fields=["status"])
        raise ValueError("Gift card has expired")
    amount = Decimal(str(card.remaining_amount))
    if amount <= 0: raise ValueError("Gift card has no remaining balance")
    tx = credit_gift_balance(
        user, amount, card.currency,
        reference=f"GIFT_CARD_REDEEM:{card.pk}:{user.pk}",
        metadata={"gift_card_id": card.pk, "user_id": user.pk, "non_withdrawable": True},
    )
    GiftCardRedemption.objects.create(gift_card=card, user=user, amount=amount)
    card.remaining_amount = Decimal("0"); card.status = GiftCard.EXHAUSTED
    card.save(update_fields=["remaining_amount", "status"])
    return tx

@transaction.atomic
def create_gift_card_purchase(*, buyer, amount, currency, recipient_email="", provider=None):
    from payments.services import initialize_payment
    amount = Decimal(str(amount))
    if amount <= 0:
        raise ValueError("Gift card amount must be positive.")
    currency = str(currency).upper().strip()
    for _ in range(5):
        code = GiftCard.generate_code()
        if not GiftCard.objects.filter(code=code).exists():
            break
    else:
        raise RuntimeError("Unable to generate a unique gift card code")
    card = GiftCard.objects.create(
        code=code,
        currency=currency,
        initial_amount=amount,
        remaining_amount=amount,
        status=GiftCard.DISABLED,
    )
    payment = initialize_payment(
        user=buyer, amount=amount, currency=currency,
        email=getattr(buyer, "email", ""), provider=provider,
        metadata={"purpose": "gift_card", "gift_card_id": card.id},
    )
    purchase = GiftCardPurchase.objects.create(
        buyer=buyer, gift_card=card, payment=payment,
        amount=amount, currency=currency, recipient_email=recipient_email,
    )
    payment.metadata = {**payment.metadata, "gift_card_purchase_id": purchase.id, "purpose": "gift_card"}
    payment.save(update_fields=["metadata"])
    return purchase


@transaction.atomic
def complete_gift_card_purchase(purchase_id):
    purchase = GiftCardPurchase.objects.select_for_update().select_related("gift_card").get(pk=purchase_id)
    if purchase.status == GiftCardPurchase.PAID:
        return purchase
    if purchase.status != GiftCardPurchase.PENDING:
        raise ValueError("Gift card purchase is not pending.")
    card = GiftCard.objects.select_for_update().get(pk=purchase.gift_card_id)
    card.status = GiftCard.ACTIVE
    card.save(update_fields=["status"])
    purchase.status = GiftCardPurchase.PAID
    purchase.paid_at = timezone.now()
    purchase.save(update_fields=["status", "paid_at"])
    return purchase

@transaction.atomic
def submit_gift_card_topup(*, user, brand, code, claimed_amount, claimed_currency, country="", user_note="", purchase_proof=""):
    from .secure_codes import encrypt_code, hash_code
    code = str(code or "").strip()
    if len(code) < 4:
        raise ValueError("Gift card code is required.")
    settings_obj = GiftCardTopUpSettings.get_solo()
    if not settings_obj.enabled:
        raise ValueError("Gift-card wallet top-ups are currently unavailable.")
    amount = Decimal(str(claimed_amount))
    if amount <= 0:
        raise ValueError("Gift card amount must be positive.")
    if amount < settings_obj.minimum_amount or (settings_obj.maximum_amount is not None and amount > settings_obj.maximum_amount):
        raise ValueError("Gift-card amount is outside the configured limits.")
    currency = str(claimed_currency or "").upper().strip()
    brand = str(brand or "").strip()
    if not brand or not currency:
        raise ValueError("Brand and currency are required.")
    if settings_obj.require_purchase_proof and not str(purchase_proof or "").strip():
        raise ValueError("Purchase proof is required for this gift-card top-up.")
    code_hash = hash_code(code)
    if GiftCardTopUp.objects.filter(code_hash=code_hash).exists():
        raise ValueError("This gift card code has already been submitted.")
    return GiftCardTopUp.objects.create(
        user=user,
        brand=brand,
        code_encrypted=encrypt_code(code),
        code_hash=code_hash,
        code_last4=code[-4:],
        claimed_amount=amount,
        claimed_currency=currency,
        country=str(country or "").upper().strip()[:3],
        user_note=str(user_note or "")[:2000],
        purchase_proof=str(purchase_proof or "")[:5000],
    )


@transaction.atomic
def review_gift_card_topup(*, topup_id, reviewer, status, approved_amount=None, approved_currency="", review_note=""):
    topup = GiftCardTopUp.objects.select_for_update().get(pk=topup_id)
    if topup.status == GiftCardTopUp.APPROVED:
        return topup
    if status not in {GiftCardTopUp.APPROVED, GiftCardTopUp.REJECTED, GiftCardTopUp.NEEDS_INFO}:
        raise ValueError("Invalid gift-card review status.")
    if status == GiftCardTopUp.APPROVED:
        amount = Decimal(str(approved_amount if approved_amount is not None else topup.claimed_amount))
        if amount <= 0:
            raise ValueError("Approved amount must be positive.")
        currency = str(approved_currency or topup.claimed_currency).upper().strip()
        from ledger.wallet_service import credit_gift_balance
        tx = credit_gift_balance(
            topup.user,
            amount,
            currency,
            reference=f"GIFT_CARD_TOPUP:{topup.pk}",
            metadata={
                "gift_card_topup_id": topup.pk,
                "brand": topup.brand,
                "verified_by": reviewer.id,
                "non_withdrawable": True,
            },
        )
        topup.approved_amount = amount
        topup.approved_currency = currency
        topup.ledger_transaction_id = tx.transaction_id
    topup.status = status
    topup.reviewed_by = reviewer
    topup.reviewed_at = timezone.now()
    topup.review_note = str(review_note or "")[:5000]
    topup.save(update_fields=[
        "status", "approved_amount", "approved_currency", "ledger_transaction_id",
        "reviewed_by", "reviewed_at", "review_note", "updated_at",
    ])
    try:
        from adminpanel.models import StaffAction
        StaffAction.objects.create(
            actor=reviewer, action=f"gift_card_topup.{status}",
            object_type="GiftCardTopUp", object_id=str(topup.pk),
            metadata={"brand": topup.brand, "amount": str(topup.approved_amount or topup.claimed_amount), "currency": topup.approved_currency or topup.claimed_currency},
        )
    except Exception:
        pass
    return topup
