from django.contrib import admin

from .wallet_models import Wallet


@admin.register(Wallet)
class WalletAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "currency",
        "ledger_account",
        "active",
        "created_at",
    )

    list_filter = (
        "currency",
        "active",
    )

    search_fields = (
        "user__username",
    )
