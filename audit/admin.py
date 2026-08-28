from django.contrib import admin
from adminpanel.admin_mixins import ShopUModelAdmin
from .models import AuditEvent
@admin.register(AuditEvent)
class AuditEventAdmin(ShopUModelAdmin): list_display=('actor','action','object_type','object_id','created_at'); search_fields=('actor__username','action','object_id'); list_filter=('action','object_type')
