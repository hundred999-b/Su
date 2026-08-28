from django.contrib import admin
from adminpanel.admin_mixins import ShopUModelAdmin
from .models import (
    LedgerAccount,
    LedgerTransaction,
    LedgerEntry,
)

admin.site.register(LedgerAccount)
admin.site.register(LedgerTransaction)
admin.site.register(LedgerEntry)

from .wallet_admin import WalletAdmin
