from django.contrib import admin
from adminpanel.admin_mixins import ShopUModelAdmin
from .models import TelegramAccount,Notification
@admin.register(TelegramAccount)
class TelegramAccountAdmin(ShopUModelAdmin): list_display=('telegram_user_id','username','user','verified','created_at'); search_fields=('username','user__username','telegram_user_id'); list_filter=('verified',)
@admin.register(Notification)
class NotificationAdmin(ShopUModelAdmin): list_display=('user','title','kind','read','created_at'); search_fields=('user__username','title','message'); list_filter=('kind','read')
