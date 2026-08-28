from django.conf import settings
from django.db import models
class CryptoDeposit(models.Model):
    PENDING, CONFIRMED, FAILED = "pending", "confirmed", "failed"
    STATUS_CHOICES = [(x, x.title()) for x in (PENDING, CONFIRMED, FAILED)]
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="crypto_deposits")
    asset = models.CharField(max_length=30)
    network = models.CharField(max_length=40, blank=True)
    amount = models.DecimalField(max_digits=24, decimal_places=12)
    address = models.CharField(max_length=255)
    tx_hash = models.CharField(max_length=255, unique=True, null=True, blank=True)
    provider = models.CharField(max_length=40, default="manual")
    provider_payment_id = models.CharField(max_length=120, unique=True, null=True, blank=True)
    price_currency = models.CharField(max_length=10, default="USD")
    pay_currency = models.CharField(max_length=30, blank=True)
    pay_amount = models.DecimalField(max_digits=24, decimal_places=12, null=True, blank=True)
    payment_url = models.URLField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    confirmations = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)

class CryptoWithdrawal(models.Model):
    PENDING, PROCESSING, COMPLETED, FAILED = "pending", "processing", "completed", "failed"
    STATUS_CHOICES = [(x, x.title()) for x in (PENDING, PROCESSING, COMPLETED, FAILED)]
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="crypto_withdrawals")
    asset = models.CharField(max_length=30)
    network = models.CharField(max_length=40, blank=True)
    amount = models.DecimalField(max_digits=24, decimal_places=12)
    fee = models.DecimalField(max_digits=24, decimal_places=12, default=0)
    destination_address = models.CharField(max_length=255)
    tx_hash = models.CharField(max_length=255, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
