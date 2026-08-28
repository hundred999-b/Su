from django.conf import settings
from django.db import models
class BankTransfer(models.Model):
    PENDING, CONFIRMED, FAILED, EXPIRED = "pending", "confirmed", "failed", "expired"
    STATUS_CHOICES = [(x, x.title()) for x in (PENDING, CONFIRMED, FAILED, EXPIRED)]
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="bank_transfers")
    amount = models.DecimalField(max_digits=18, decimal_places=2)
    currency = models.CharField(max_length=10, default="USD")
    reference = models.CharField(max_length=160, unique=True)
    provider_reference = models.CharField(max_length=160, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
