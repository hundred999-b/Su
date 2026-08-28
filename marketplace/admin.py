from django.contrib import admin
from adminpanel.admin_mixins import ShopUModelAdmin
from .models import Product, Order, ListingPolicy, ListingVersion

@admin.register(ListingPolicy)
class ListingPolicyAdmin(ShopUModelAdmin):
    list_display = ("title", "version", "active", "updated_at")
    list_filter = ("active",)
    search_fields = ("title", "content")

@admin.register(Product)
class ProductAdmin(ShopUModelAdmin):
    list_display = ("title", "seller", "category", "condition", "price", "currency", "active", "version", "published_at")
    search_fields = ("title", "description", "seller__username")
    list_filter = ("category", "condition", "active", "currency", "disclosure_acknowledged", "fee_acknowledged")
    readonly_fields = ("version", "listing_policy_version", "listing_policy_content", "published_at", "created_at", "updated_at")

@admin.register(ListingVersion)
class ListingVersionAdmin(ShopUModelAdmin):
    list_display = ("product", "version", "price", "currency", "policy_version", "created_at")
    search_fields = ("product__title", "description", "seller_terms", "policy_content")
    list_filter = ("currency", "policy_version")
    readonly_fields = [f.name for f in ListingVersion._meta.fields]

@admin.register(Order)
class OrderAdmin(ShopUModelAdmin):
    list_display = ("id", "buyer", "product", "amount", "currency", "listing_version", "status", "buyer_disclosure_acknowledged_at", "confirmation_deadline")
    search_fields = ("buyer__username", "product__title", "description_snapshot")
    list_filter = ("status", "currency")
    readonly_fields = ("listing_version", "product_title_snapshot", "description_snapshot", "condition_snapshot", "specifications_snapshot", "seller_terms_snapshot", "policy_version_snapshot", "policy_content_snapshot", "buyer_disclosure_acknowledged_at")
