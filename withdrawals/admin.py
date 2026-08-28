from django.contrib import admin, messages
from .models import WithdrawalRequest
from .services import complete_withdrawal, fail_withdrawal
from adminpanel.admin_mixins import ShopUModelAdmin, _allowed

@admin.action(description="Mark selected withdrawals as processing")
def mark_processing(modeladmin, request, queryset):
    if not request.user.is_superuser and not _allowed(request, WithdrawalRequest, "approve"):
        messages.error(request, "You do not have permission to approve withdrawals.")
        return
    queryset.filter(status=WithdrawalRequest.PENDING).update(status=WithdrawalRequest.PROCESSING)

@admin.action(description="Complete selected withdrawals")
def complete(modeladmin, request, queryset):
    if not request.user.is_superuser and not _allowed(request, WithdrawalRequest, "approve"):
        messages.error(request, "You do not have permission to complete withdrawals.")
        return
    for req in queryset.filter(status=WithdrawalRequest.PROCESSING):
        try:
            complete_withdrawal(req.pk, provider_reference="ADMIN")
        except Exception as exc:
            messages.error(request, f"Withdrawal #{req.pk}: {exc}")

@admin.action(description="Fail and return funds")
def fail(modeladmin, request, queryset):
    if not request.user.is_superuser and not _allowed(request, WithdrawalRequest, "reject"):
        messages.error(request, "You do not have permission to reject withdrawals.")
        return
    for req in queryset.filter(status__in=[WithdrawalRequest.PENDING, WithdrawalRequest.PROCESSING]):
        try:
            fail_withdrawal(req.pk, "Rejected by staff")
        except Exception as exc:
            messages.error(request, f"Withdrawal #{req.pk}: {exc}")

@admin.register(WithdrawalRequest)
class WithdrawalRequestAdmin(ShopUModelAdmin):
    list_display = ("user", "amount", "fee", "currency", "method", "status", "created_at")
    list_filter = ("status", "method", "currency")
    search_fields = ("user__username", "provider_reference", "destination_reference")
    readonly_fields = ("created_at", "updated_at")
    actions = (mark_processing, complete, fail)
