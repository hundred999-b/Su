from django.contrib import admin
from adminpanel.admin_mixins import ShopUModelAdmin
from .models import FinanceSettings, PaymentMethodConfig, CryptoAssetConfig, CommissionRule, SupportedCurrency, PaymentGatewayConfig, PayoutProviderConfig

@admin.register(FinanceSettings)
class FinanceSettingsAdmin(ShopUModelAdmin):
    readonly_fields = ("updated_at",)
    list_display = ("default_currency", "bank_transfer_enabled", "card_enabled", "crypto_enabled", "gift_cards_enabled", "updated_at")
    fieldsets = (
        ("General", {"fields": ("default_currency", "escrow_auto_release_hours")} ),
        ("Deposit limits", {"fields": ("min_deposit", "max_deposit")} ),
        ("Withdrawal limits", {"fields": ("min_withdrawal", "max_withdrawal", "withdrawal_fee")} ),
        ("Payment rails", {"fields": ("bank_transfer_enabled", "card_enabled", "crypto_enabled", "gift_cards_enabled")} ),
    )
    def has_add_permission(self, request):
        return not FinanceSettings.objects.exists()

@admin.register(PaymentMethodConfig)
class PaymentMethodConfigAdmin(ShopUModelAdmin):
    list_display = ("name", "key", "enabled", "display_order")
    list_filter = ("enabled",)
    search_fields = ("name", "key")

@admin.register(CryptoAssetConfig)
class CryptoAssetConfigAdmin(ShopUModelAdmin):
    list_display = ("asset", "network", "enabled", "confirmation_count", "min_deposit", "min_withdrawal", "withdrawal_fee")
    list_filter = ("enabled", "asset")

@admin.register(CommissionRule)
class CommissionRuleAdmin(ShopUModelAdmin):
    list_display = ("name", "fee_type", "percentage", "fixed_amount", "currency", "enabled")
    list_filter = ("fee_type", "enabled", "currency")
    search_fields = ("name",)

@admin.register(SupportedCurrency)
class SupportedCurrencyAdmin(ShopUModelAdmin):
    list_display = ("code", "name", "symbol", "decimal_places", "enabled", "is_default")
    list_filter = ("enabled", "is_default", "decimal_places")
    search_fields = ("code", "name")

@admin.register(PaymentGatewayConfig)
class PaymentGatewayConfigAdmin(ShopUModelAdmin):
    list_display = ("provider", "enabled", "priority", "updated_at")
    list_filter = ("enabled",)
    search_fields = ("provider",)


@admin.register(PayoutProviderConfig)
class PayoutProviderConfigAdmin(ShopUModelAdmin):
    list_display = (
        "name",
        "provider",
        "enabled",
        "priority",
        "supported_currencies",
        "min_amount",
        "max_amount",
        "updated_at",
    )
    list_filter = ("enabled",)
    search_fields = ("name", "provider")
    readonly_fields = ("updated_at",)
    list_editable = ("enabled", "priority")
