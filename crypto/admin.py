from django.contrib import admin
from adminpanel.admin_mixins import ShopUModelAdmin
from .models import CryptoDeposit, CryptoWithdrawal
@admin.register(CryptoDeposit)
class CryptoDepositAdmin(ShopUModelAdmin):
    list_display = ("user", "asset", "network", "amount", "confirmations", "status", "created_at")
    list_filter = ("asset", "network", "status")
    search_fields = ("user__username", "tx_hash", "address")
@admin.register(CryptoWithdrawal)
class CryptoWithdrawalAdmin(ShopUModelAdmin):
    list_display = ("user", "asset", "network", "amount", "fee", "status", "created_at")
    list_filter = ("asset", "network", "status")
    search_fields = ("user__username", "tx_hash", "destination_address")
