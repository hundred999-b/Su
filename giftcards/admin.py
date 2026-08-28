from django.contrib import admin
from adminpanel.admin_mixins import ShopUModelAdmin, _allowed
from .models import GiftCard, GiftCardRedemption, GiftCardPurchase, GiftCardTopUp, GiftCardTopUpSettings
@admin.register(GiftCard)
class GiftCardAdmin(ShopUModelAdmin):
    readonly_fields = ("code", "remaining_amount", "created_at")
    list_display = ("code", "currency", "initial_amount", "remaining_amount", "status", "expires_at", "created_at")
    list_filter = ("status", "currency")
    search_fields = ("code",)
@admin.register(GiftCardRedemption)
class GiftCardRedemptionAdmin(ShopUModelAdmin):
    list_display = ("gift_card", "user", "amount", "created_at")
    search_fields = ("gift_card__code", "user__username")
    readonly_fields = ("gift_card", "user", "amount", "created_at")

@admin.register(GiftCardPurchase)
class GiftCardPurchaseAdmin(ShopUModelAdmin):
    list_display = ("id", "buyer", "gift_card", "amount", "currency", "status", "created_at", "paid_at")
    list_filter = ("status", "currency")
    search_fields = ("buyer__username", "gift_card__code", "payment__provider_reference", "recipient_email")
    readonly_fields = [f.name for f in GiftCardPurchase._meta.fields]

@admin.register(GiftCardTopUp)
class GiftCardTopUpAdmin(ShopUModelAdmin):
    list_display = ("id", "user", "brand", "code_last4", "claimed_amount", "claimed_currency", "status", "reviewed_by", "created_at")
    list_filter = ("status", "brand", "claimed_currency")
    search_fields = ("user__username", "brand", "code_hash", "code_last4")
    readonly_fields = ("user", "brand", "code_for_review", "code_encrypted", "code_hash", "code_last4", "claimed_amount", "claimed_currency", "country", "purchase_proof", "created_at", "updated_at", "ledger_transaction_id", "reviewed_by", "reviewed_at")
    fieldsets = (
        ("Submission", {"fields": (
            "user",
            "brand",
            "code_last4",
            "claimed_amount",
            "claimed_currency",
            "country",
            "user_note",
            "purchase_proof",
            "created_at",
        )}),
        ("Secure code", {"fields": (
            "code_for_review",
            "code_encrypted",
            "code_hash",
        )}),
        ("Review", {"fields": (
            "status",
            "approved_amount",
            "approved_currency",
            "review_note",
            "reviewed_by",
            "reviewed_at",
            "ledger_transaction_id",
        )}),
    )

    @admin.display(description="Gift card code (authorized staff only)")
    def code_for_review(self, obj):
        try:
            return obj.code
        except Exception:
            return "[unavailable]"

    def save_model(self, request, obj, form, change):
        if not request.user.is_superuser and not _allowed(request, GiftCardTopUp, "review"):
            raise PermissionError("You do not have permission to review gift-card top-ups.")

        if not change:
            return super().save_model(request, obj, form, change)

        from .services import review_gift_card_topup

        requested_status = obj.status

        if requested_status in {
            GiftCardTopUp.APPROVED,
            GiftCardTopUp.REJECTED,
            GiftCardTopUp.NEEDS_INFO,
        }:
            updated = review_gift_card_topup(
                topup_id=obj.pk,
                reviewer=request.user,
                status=requested_status,
                approved_amount=(
                    obj.approved_amount
                    if obj.approved_amount is not None
                    else obj.claimed_amount
                ),
                approved_currency=(
                    obj.approved_currency
                    or obj.claimed_currency
                ),
                review_note=obj.review_note,
            )

            obj.status = updated.status
            obj.approved_amount = updated.approved_amount
            obj.approved_currency = updated.approved_currency
            obj.ledger_transaction_id = updated.ledger_transaction_id
            obj.reviewed_by = updated.reviewed_by
            obj.reviewed_at = updated.reviewed_at
            obj.review_note = updated.review_note
            return

        super().save_model(request, obj, form, change)

@admin.register(GiftCardTopUpSettings)
class GiftCardTopUpSettingsAdmin(ShopUModelAdmin):
    list_display = ("enabled", "manual_review_required", "minimum_amount", "maximum_amount", "require_purchase_proof", "updated_at")
    fieldsets = (("Wallet top-up", {"fields": ("enabled", "manual_review_required", "minimum_amount", "maximum_amount", "require_purchase_proof")}),)
