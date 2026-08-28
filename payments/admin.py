from django.contrib import admin
from adminpanel.admin_mixins import ShopUModelAdmin

from .models import Payment


@admin.register(Payment)
class PaymentAdmin(ShopUModelAdmin):
    list_display = (
        "user", "provider", "provider_reference",
        "amount", "currency", "status", "created_at",
    )
    search_fields = (
        "user__username", "provider_reference",
        "provider", "idempotency_key",
    )
    list_filter = ("provider", "status", "currency")
    readonly_fields = (
        "created_at", "authorization_url", "access_code", "metadata",
    )
