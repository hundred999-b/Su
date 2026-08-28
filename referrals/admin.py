from django.contrib import admin
from adminpanel.admin_mixins import ShopUModelAdmin
from .models import ReferralProfile, ReferralProgramSettings, ReferralReward

@admin.register(ReferralProgramSettings)
class ReferralProgramSettingsAdmin(ShopUModelAdmin):
    list_display = ("enabled", "transactions_limit", "commission_percent", "updated_at")

@admin.register(ReferralProfile)
class ReferralProfileAdmin(ShopUModelAdmin):
    list_display = ("user", "code", "referred_by", "eligible_transactions_count", "total_earned_by_currency", "attributed_at")
    search_fields = ("user__username", "code", "referred_by__username")
    readonly_fields = ("code", "created_at", "attributed_at")

@admin.register(ReferralReward)
class ReferralRewardAdmin(ShopUModelAdmin):
    list_display = ("id", "referrer", "referred_user", "order", "sequence", "amount", "currency", "created_at")
    search_fields = ("referrer__username", "referred_user__username", "order__id", "ledger_transaction_id")
    readonly_fields = [f.name for f in ReferralReward._meta.fields]
