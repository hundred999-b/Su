import secrets
from decimal import Decimal
from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models

class GiftCard(models.Model):
    ACTIVE, DISABLED, EXHAUSTED, EXPIRED = "active", "disabled", "exhausted", "expired"
    STATUS_CHOICES = [(x, x.title()) for x in (ACTIVE, DISABLED, EXHAUSTED, EXPIRED)]
    code = models.CharField(max_length=64, unique=True, db_index=True)
    currency = models.CharField(max_length=10, default="USD")
    initial_amount = models.DecimalField(max_digits=24, decimal_places=8, validators=[MinValueValidator(Decimal("0.01"))])
    remaining_amount = models.DecimalField(max_digits=24, decimal_places=8, validators=[MinValueValidator(Decimal("0"))])
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=ACTIVE)
    expires_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    def __str__(self): return self.code
    @staticmethod
    def generate_code():
        return secrets.token_urlsafe(24).replace("-", "").replace("_", "")[:32].upper()

class GiftCardRedemption(models.Model):
    gift_card = models.ForeignKey(GiftCard, on_delete=models.PROTECT, related_name="redemptions")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="gift_card_redemptions")
    amount = models.DecimalField(max_digits=24, decimal_places=8, validators=[MinValueValidator(Decimal("0.01"))])
    created_at = models.DateTimeField(auto_now_add=True)

class GiftCardPurchase(models.Model):
    PENDING, PAID, FAILED, CANCELLED = "pending", "paid", "failed", "cancelled"
    STATUS_CHOICES = [(x, x.title()) for x in (PENDING, PAID, FAILED, CANCELLED)]
    buyer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="gift_card_purchases")
    gift_card = models.OneToOneField(GiftCard, on_delete=models.PROTECT, related_name="purchase")
    payment = models.OneToOneField("payments.Payment", on_delete=models.PROTECT, related_name="gift_card_purchase")
    amount = models.DecimalField(max_digits=24, decimal_places=8, validators=[MinValueValidator(Decimal("0.01"))])
    currency = models.CharField(max_length=10)
    recipient_email = models.EmailField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    paid_at = models.DateTimeField(null=True, blank=True)
from decimal import Decimal
from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models

# Existing GiftCard/GiftCardRedemption/GiftCardPurchase stay unchanged.

class GiftCardTopUp(models.Model):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    NEEDS_INFO = "needs_info"
    STATUS_CHOICES = [(x, x.replace('_', ' ').title()) for x in (PENDING, APPROVED, REJECTED, NEEDS_INFO)]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="gift_card_topups")
    brand = models.CharField(max_length=120)
    code_encrypted = models.TextField()
    code_hash = models.CharField(max_length=64, unique=True, db_index=True)
    code_last4 = models.CharField(max_length=8, blank=True)
    claimed_amount = models.DecimalField(max_digits=24, decimal_places=8, validators=[MinValueValidator(Decimal("0.01"))])
    claimed_currency = models.CharField(max_length=10)
    approved_amount = models.DecimalField(max_digits=24, decimal_places=8, null=True, blank=True, validators=[MinValueValidator(Decimal("0.01"))])
    approved_currency = models.CharField(max_length=10, blank=True)
    country = models.CharField(max_length=3, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=PENDING, db_index=True)
    user_note = models.TextField(blank=True)
    purchase_proof = models.TextField(blank=True)
    review_note = models.TextField(blank=True)
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="gift_card_topups_reviewed")
    reviewed_at = models.DateTimeField(null=True, blank=True)
    ledger_transaction_id = models.CharField(max_length=64, unique=True, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    @property
    def code(self):
        from .secure_codes import decrypt_code
        return decrypt_code(self.code_encrypted)

    def __str__(self):
        return f"{self.brand} • {self.user.username} • {self.status}"

class GiftCardTopUpSettings(models.Model):
    singleton = models.BooleanField(default=True, unique=True, editable=False)
    enabled = models.BooleanField(default=True)
    manual_review_required = models.BooleanField(default=True)
    minimum_amount = models.DecimalField(max_digits=24, decimal_places=8, default=1)
    maximum_amount = models.DecimalField(max_digits=24, decimal_places=8, null=True, blank=True)
    require_purchase_proof = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def get_solo(cls):
        return cls.objects.get_or_create(pk=1)[0]

    def __str__(self):
        return "Gift Card Wallet Top-Up Settings"
