from django.contrib import admin
from adminpanel.admin_mixins import ShopUModelAdmin
from .models import Profile

@admin.register(Profile)
class ProfileAdmin(ShopUModelAdmin):
    list_display = ('user', 'role', 'verified', 'suspended', 'completed_transactions', 'dispute_count', 'last_seen_at')
    search_fields = ('user__username', 'user__email', 'telegram_id', 'phone')
    list_filter = ('role', 'verified', 'suspended')

    @admin.display(description='Completed')
    def completed_transactions(self, obj):
        from marketplace.models import Order
        return Order.objects.filter(product__seller=obj.user, status=Order.COMPLETED).count()

    @admin.display(description='Disputes')
    def dispute_count(self, obj):
        from stage4.models import DisputeEvent
        return DisputeEvent.objects.filter(order__product__seller=obj.user, event_type='opened').count()
