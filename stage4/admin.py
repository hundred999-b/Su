from django.contrib import admin
from adminpanel.admin_mixins import ShopUModelAdmin
from .models import TermsDocument,TermsAcceptance,ListingRule,ListingVersion,OrderListingSnapshot,NotificationDelivery,DisputeEvent,AdminAnnouncement

@admin.register(TermsDocument)
class TermsDocumentAdmin(ShopUModelAdmin):
    list_display=("kind","version","title","active","created_by","created_at")
    list_filter=("kind","active")
    search_fields=("version","title","body")
    actions=["activate_selected"]
    @admin.action(description="Activate selected terms")
    def activate_selected(self,request,queryset):
        for obj in queryset:
            TermsDocument.objects.filter(kind=obj.kind).update(active=False)
            obj.active=True; obj.save(update_fields=["active"])

@admin.register(TermsAcceptance)
class TermsAcceptanceAdmin(ShopUModelAdmin):
    list_display=("user","terms","purpose","accepted_at")
    list_filter=("purpose","terms__kind")
    search_fields=("user__username","terms__version")

@admin.register(ListingRule)
class ListingRuleAdmin(ShopUModelAdmin):
    list_display=("min_description_chars","max_description_chars","require_accuracy_confirmation","require_seller_terms","updated_at")
    fieldsets=((None,{"fields":("min_description_chars","max_description_chars","require_accuracy_confirmation","require_seller_terms","lock_title_after_order","lock_description_after_order","lock_price_after_order","prohibited_keywords")}),)

@admin.register(ListingVersion)
class ListingVersionAdmin(ShopUModelAdmin):
    list_display=("product","version","price","currency","accuracy_confirmed","fee_disclosed","published_at")
    search_fields=("product__title","product__seller__username")

@admin.register(OrderListingSnapshot)
class OrderListingSnapshotAdmin(ShopUModelAdmin):
    list_display=("order","product","listing_version","price","currency","captured_at")
    readonly_fields=("order","product","listing_version","title","description","category","price","currency","captured_at")

@admin.register(NotificationDelivery)
class NotificationDeliveryAdmin(ShopUModelAdmin):
    list_display=("notification","channel","status","attempts","sent_at","updated_at")
    list_filter=("channel","status")

@admin.register(DisputeEvent)
class DisputeEventAdmin(ShopUModelAdmin):
    list_display=("order","actor","event_type","created_at")
    list_filter=("event_type",)

@admin.register(AdminAnnouncement)
class AdminAnnouncementAdmin(ShopUModelAdmin):
    list_display=("title","active","created_by","created_at")
    list_filter=("active",)
    search_fields=("title","message")
