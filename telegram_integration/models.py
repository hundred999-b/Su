from django.conf import settings
from django.db import models

class TelegramAccount(models.Model):
    telegram_user_id = models.BigIntegerField(unique=True)
    username = models.CharField(max_length=255, blank=True)
    verified = models.BooleanField(default=False)
    verified_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    user = models.OneToOneField(settings.AUTH_USER_MODEL,on_delete=models.CASCADE,related_name='telegram_account')

class Notification(models.Model):
    user=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.CASCADE,related_name='notifications')
    kind=models.CharField(max_length=80)
    title=models.CharField(max_length=160)
    message=models.TextField()
    read=models.BooleanField(default=False)
    created_at=models.DateTimeField(auto_now_add=True)
