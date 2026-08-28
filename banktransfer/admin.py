from django.contrib import admin, messages
from .models import BankTransfer
from .services import confirm_deposit, fail_transfer
from adminpanel.admin_mixins import ShopUModelAdmin, _allowed

@admin.action(description="Confirm selected bank transfers")
def confirm_transfers(modeladmin, request, queryset):
    if not request.user.is_superuser and not _allowed(request, BankTransfer, "approve"):
        messages.error(request, "You do not have permission to approve bank transfers.")
        return
    for transfer in queryset.filter(status=BankTransfer.PENDING):
        try:
            confirm_deposit(transfer_id=transfer.pk)
        except Exception as exc:
            messages.error(request, f"Transfer #{transfer.pk}: {exc}")

@admin.action(description="Fail selected bank transfers")
def fail_transfers(modeladmin, request, queryset):
    if not request.user.is_superuser and not _allowed(request, BankTransfer, "reject"):
        messages.error(request, "You do not have permission to reject bank transfers.")
        return
    for transfer in queryset.filter(status=BankTransfer.PENDING):
        fail_transfer(transfer.pk, "Rejected by staff")

@admin.register(BankTransfer)
class BankTransferAdmin(ShopUModelAdmin):
    list_display = ("user", "amount", "currency", "reference", "status", "created_at")
    list_filter = ("status", "currency")
    search_fields = ("user__username", "reference", "provider_reference")
    actions = (confirm_transfers, fail_transfers)
    readonly_fields = ("reference", "created_at", "confirmed_at")
