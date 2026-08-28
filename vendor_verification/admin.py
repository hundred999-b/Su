from django.contrib import admin
from django.utils import timezone
from adminpanel.admin_mixins import ShopUModelAdmin, _allowed
from .models import (
    VendorVerification,
    VendorComplaint,
    VendorTrustSettings,
    VerificationProgramSettings,
    VerificationStep,
    VerificationStepResult,
)
from .services import set_vendor_status


@admin.register(VerificationProgramSettings)
class VerificationProgramSettingsAdmin(ShopUModelAdmin):
    list_display = ("enabled", "minimum_completed_transactions", "updated_at")
    fieldsets = (("Program", {"fields": ("enabled", "minimum_completed_transactions")}), ("Legacy built-in toggles", {"fields": ("require_identity", "require_business", "require_payment_history", "require_transaction_history"), "description": "These four toggles remain for compatibility. Use Verification Steps below to add or change the process."}),)


@admin.register(VendorTrustSettings)
class VendorTrustSettingsAdmin(ShopUModelAdmin):
    list_display = ("caution_dispute_threshold", "caution_complaint_threshold", "caution_dispute_rate_percent", "updated_at")
    fieldsets = (("Automatic caution thresholds", {"fields": ("caution_dispute_threshold", "caution_complaint_threshold", "caution_dispute_rate_percent"), "description": "A caution signal is shown automatically when a seller reaches any threshold. Admin overrides on an individual vendor take precedence."}),)

    def save_model(self, request, obj, form, change):
        obj.save()


@admin.register(VerificationStep)
class VerificationStepAdmin(ShopUModelAdmin):
    list_display = ("order", "name", "key", "enabled", "required", "evidence_type")
    list_editable = ("enabled", "required", "order")
    list_display_links = ("name",)
    search_fields = ("name", "key", "description")
    list_filter = ("enabled", "required", "evidence_type")


@admin.register(VerificationStepResult)
class VerificationStepResultAdmin(ShopUModelAdmin):
    list_display = ("verification", "step", "status", "reviewed_by", "reviewed_at")
    list_filter = ("status", "step")
    search_fields = ("verification__seller__username", "step__name", "evidence")


@admin.register(VendorVerification)
class VendorVerificationAdmin(ShopUModelAdmin):
    list_display = ("seller", "status", "caution_display", "completed_transactions", "dispute_count", "open_complaints", "verified_by", "trusted_by", "verified_at", "trusted_at")
    search_fields = ("seller__username", "seller__email", "trusted_reason", "caution_note")
    list_filter = ("status", "caution_override")
    actions = ["promote_trusted", "mark_verified", "demote_to_verified", "suspend_selected", "revoke_selected", "force_caution", "clear_caution_override"]
    fieldsets = (
        ("Vendor status", {"fields": ("seller", "status", "notes", "trusted_reason", "trusted_by", "trusted_at", "verified_by", "verified_at", "revoked_at")}),
        ("Verification evidence", {"fields": ("identity_verified", "business_verified", "payment_history_verified", "transaction_history_verified")}),
        ("Caution signal", {"fields": ("caution_override", "caution_note"), "description": "Leave override empty for automatic risk calculation. True forces a caution signal; False suppresses automatic caution."}),
    )

    @admin.display(description="Caution")
    def caution_display(self, obj):
        from .trust import vendor_has_caution
        return "⚠ Caution" if vendor_has_caution(obj.seller, obj) else "—"

    @admin.display(description="Completed")
    def completed_transactions(self, obj):
        from marketplace.models import Order
        return Order.objects.filter(product__seller=obj.seller, status=Order.COMPLETED).count()

    @admin.display(description="Disputes")
    def dispute_count(self, obj):
        from stage4.models import DisputeEvent
        return DisputeEvent.objects.filter(order__product__seller=obj.seller, event_type="opened").values("order_id").distinct().count()

    @admin.display(description="Open complaints")
    def open_complaints(self, obj):
        return obj.seller.vendor_complaints.filter(status__in=[VendorComplaint.OPEN, VendorComplaint.SUBSTANTIATED]).count()

    def save_model(self, request, obj, form, change):
        if not request.user.is_superuser and not _allowed(request, VendorVerification, "verify"):
            raise PermissionError("You do not have permission to review vendor verification.")
        values = {
            "identity_verified": obj.identity_verified,
            "business_verified": obj.business_verified,
            "payment_history_verified": obj.payment_history_verified,
            "transaction_history_verified": obj.transaction_history_verified,
        }
        updated = set_vendor_status(
            obj.seller, obj.status, reviewer=request.user, note=obj.trusted_reason or obj.notes, **values
        )
        # Preserve explicit admin caution controls from the form.
        updated.caution_override = obj.caution_override
        updated.caution_note = obj.caution_note
        updated.trusted_reason = obj.trusted_reason
        updated.save(update_fields=["caution_override", "caution_note", "trusted_reason", "updated_at"])
        form.instance.pk = updated.pk

    @admin.action(description="Promote selected to Trusted Vendor")
    def promote_trusted(self, request, queryset):
        for obj in queryset.select_related("seller"):
            set_vendor_status(obj.seller, VendorVerification.TRUSTED, reviewer=request.user, note=obj.trusted_reason or "Promoted by ShopU admin.")

    @admin.action(description="Mark selected Verified Vendor")
    def mark_verified(self, request, queryset):
        for obj in queryset.select_related("seller"):
            set_vendor_status(obj.seller, VendorVerification.VERIFIED, reviewer=request.user, note=obj.notes)

    @admin.action(description="Demote selected to Verified Vendor")
    def demote_to_verified(self, request, queryset):
        for obj in queryset.select_related("seller"):
            set_vendor_status(obj.seller, VendorVerification.VERIFIED, reviewer=request.user, note=obj.notes)

    @admin.action(description="Suspend selected vendors")
    def suspend_selected(self, request, queryset):
        for obj in queryset.select_related("seller"):
            set_vendor_status(obj.seller, VendorVerification.SUSPENDED, reviewer=request.user, note=obj.notes)

    @admin.action(description="Revoke selected verification")
    def revoke_selected(self, request, queryset):
        for obj in queryset.select_related("seller"):
            set_vendor_status(obj.seller, VendorVerification.REVOKED, reviewer=request.user, note=obj.notes)

    @admin.action(description="Force caution on selected vendors")
    def force_caution(self, request, queryset):
        queryset.update(caution_override=True, caution_note="Manually flagged by ShopU admin.", updated_at=timezone.now())

    @admin.action(description="Clear caution override; return to automatic rules")
    def clear_caution_override(self, request, queryset):
        queryset.update(caution_override=None, caution_note="", updated_at=timezone.now())


@admin.register(VendorComplaint)
class VendorComplaintAdmin(ShopUModelAdmin):
    list_display = ("id", "seller", "category", "severity", "status", "order", "reviewed_by", "created_at", "resolved_at")
    list_filter = ("status", "severity", "category")
    search_fields = ("seller__username", "reporter__username", "description", "resolution_note")
    readonly_fields = ("created_at", "updated_at")
    actions = ["mark_substantiated", "dismiss_selected", "resolve_selected"]

    @admin.action(description="Mark complaints substantiated")
    def mark_substantiated(self, request, queryset):
        queryset.update(status=VendorComplaint.SUBSTANTIATED, reviewed_by=request.user, updated_at=timezone.now())

    @admin.action(description="Dismiss selected complaints")
    def dismiss_selected(self, request, queryset):
        queryset.update(status=VendorComplaint.DISMISSED, reviewed_by=request.user, updated_at=timezone.now())

    @admin.action(description="Resolve selected complaints")
    def resolve_selected(self, request, queryset):
        queryset.update(status=VendorComplaint.RESOLVED, reviewed_by=request.user, resolved_at=timezone.now(), updated_at=timezone.now())
