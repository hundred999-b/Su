from django.contrib import admin
from adminpanel.admin_mixins import ShopUModelAdmin
from .models import Review
@admin.register(Review)
class ReviewAdmin(ShopUModelAdmin): list_display=('id','buyer','seller','rating','visible','edited','created_at'); search_fields=('buyer__username','seller__username','comment'); list_filter=('rating','visible','edited')
