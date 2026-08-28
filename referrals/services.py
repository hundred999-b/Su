from decimal import Decimal, ROUND_DOWN
from django.db import transaction
from django.utils import timezone
from ledger.models import LedgerAccount, LedgerEntry
from ledger.services import create_transaction
from marketplace.models import Order
from .models import ReferralProfile, ReferralProgramSettings, ReferralReward


def _quantize_currency(amount, currency):
    try:
        from finance.models import SupportedCurrency
        cfg = SupportedCurrency.objects.filter(code=currency.upper()).first()
        places = cfg.decimal_places if cfg else 2
    except Exception:
        places = 2
    quantum = Decimal(1).scaleb(-places)
    return amount.quantize(quantum, rounding=ROUND_DOWN)

def ensure_referral_profile(user):
    profile, _ = ReferralProfile.objects.get_or_create(user=user)
    return profile

@transaction.atomic
def attribute_referral(referred_user, referral_code):
    if not referral_code:
        return ensure_referral_profile(referred_user)
    profile = ensure_referral_profile(referred_user)
    if profile.referred_by_id:
        return profile
    if Order.objects.filter(
        buyer=referred_user, status=Order.COMPLETED
    ).exists():
        return profile
    referrer_profile = ReferralProfile.objects.select_related("user").filter(code=referral_code.strip()).first()
    if not referrer_profile or referrer_profile.user_id == referred_user.id:
        return profile
    profile.referred_by = referrer_profile.user
    profile.attributed_at = timezone.now()
    profile.save(update_fields=["referred_by", "attributed_at"])
    return profile

def referral_link(bot_username, user):
    profile = ensure_referral_profile(user)
    return f"https://t.me/{bot_username}?start=ref_{profile.code}"

@transaction.atomic
def award_referral_commission(order_id):
    order = Order.objects.select_for_update().select_related("buyer").get(pk=order_id)
    if order.status != Order.COMPLETED or ReferralReward.objects.filter(order=order).exists():
        return None
    referral = ReferralProfile.objects.select_for_update().filter(user_id=order.buyer_id, referred_by__isnull=False).first()
    if not referral:
        return None
    program = ReferralProgramSettings.get_solo()
    if not program.enabled or referral.eligible_transactions_count >= program.transactions_limit:
        return None
    sequence = referral.eligible_transactions_count + 1
    base = Decimal(str(order.amount))
    rate = Decimal(str(program.commission_percent))
    currency = order.currency.upper()
    reward = _quantize_currency(base * rate / Decimal("100"), currency)
    referral.eligible_transactions_count = sequence
    if reward <= 0:
        referral.save(update_fields=["eligible_transactions_count"])
        return None

    from ledger.wallet_service import ensure_wallet
    wallet = ensure_wallet(referral.referred_by, currency).ledger_account
    expense, _ = LedgerAccount.objects.get_or_create(
        name="REFERRAL_REWARDS", currency=currency,
        defaults={"account_type": LedgerAccount.EXPENSE},
    )
    tx = create_transaction(
        description=f"Referral reward #{sequence} for order #{order.id}",
        reference=f"REFERRAL_REWARD:{order.id}",
        postings=[
            {"account": expense, "direction": LedgerEntry.DEBIT, "amount": reward},
            {"account": wallet, "direction": LedgerEntry.CREDIT, "amount": reward},
        ],
        metadata={
            "order_id": order.id,
            "referrer_id": referral.referred_by_id,
            "referred_user_id": order.buyer_id,
            "sequence": sequence,
            "commission_percent": str(rate),
            "base_amount": str(base),
        },
    )
    ReferralReward.objects.create(
        referral=referral, referrer_id=referral.referred_by_id,
        referred_user_id=order.buyer_id, order=order, sequence=sequence,
        base_amount=base, commission_percent=rate, amount=reward,
        currency=currency, ledger_transaction_id=tx.transaction_id,
    )
    totals = dict(referral.total_earned_by_currency or {})
    totals[currency] = str(Decimal(str(totals.get(currency, "0"))) + reward)
    referral.total_earned_by_currency = totals
    referral.save(update_fields=["eligible_transactions_count", "total_earned_by_currency"])
    return tx
