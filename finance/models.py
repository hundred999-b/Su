from decimal import Decimal
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models


class FinanceSettings(models.Model):
    """Global ShopU financial rules. Keep secrets out of this model."""
    singleton = models.BooleanField(default=True, unique=True, editable=False)
    default_currency = models.CharField(max_length=10, default="USD")
    escrow_auto_release_hours = models.PositiveIntegerField(default=6)
    min_deposit = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal("1.00"), validators=[MinValueValidator(Decimal("0"))])
    max_deposit = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(Decimal("0"))])
    min_withdrawal = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal("10.00"), validators=[MinValueValidator(Decimal("0"))])
    max_withdrawal = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(Decimal("0"))])
    withdrawal_fee = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal("0.00"), validators=[MinValueValidator(Decimal("0"))])
    gift_cards_enabled = models.BooleanField(default=True)
    crypto_enabled = models.BooleanField(default=False)
    bank_transfer_enabled = models.BooleanField(default=True)
    card_enabled = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def get_solo(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def __str__(self):
        return "ShopU Finance Settings"


class PaymentMethodConfig(models.Model):
    key = models.CharField(max_length=40, unique=True)
    name = models.CharField(max_length=80)
    enabled = models.BooleanField(default=False)
    display_order = models.PositiveIntegerField(default=0)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["display_order", "name"]

    def __str__(self):
        return f"{self.name} ({'on' if self.enabled else 'off'})"


class CryptoAssetConfig(models.Model):
    asset = models.CharField(max_length=30, unique=True)
    enabled = models.BooleanField(default=False)
    network = models.CharField(max_length=40, blank=True)
    min_deposit = models.DecimalField(max_digits=24, decimal_places=12, default=Decimal("0"), validators=[MinValueValidator(Decimal("0"))])
    min_withdrawal = models.DecimalField(max_digits=24, decimal_places=12, default=Decimal("0"), validators=[MinValueValidator(Decimal("0"))])
    confirmation_count = models.PositiveIntegerField(default=1)
    withdrawal_fee = models.DecimalField(max_digits=24, decimal_places=12, default=Decimal("0"), validators=[MinValueValidator(Decimal("0"))])

    def __str__(self):
        return f"{self.asset} ({self.network or 'default'})"


class CommissionRule(models.Model):
    MARKETPLACE = "marketplace"
    ESCROW = "escrow"
    PAYMENT = "payment"
    TYPES = [(MARKETPLACE, "Marketplace"), (ESCROW, "Escrow"), (PAYMENT, "Payment")]
    name = models.CharField(max_length=100, unique=True)
    fee_type = models.CharField(max_length=20, choices=TYPES)
    percentage = models.DecimalField(max_digits=7, decimal_places=4, default=Decimal("0"), validators=[MinValueValidator(Decimal("0")), MaxValueValidator(Decimal("100"))])
    fixed_amount = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal("0"), validators=[MinValueValidator(Decimal("0"))])
    currency = models.CharField(max_length=10, default="USD")
    enabled = models.BooleanField(default=True)

    def __str__(self):
        return self.name

class SupportedCurrency(models.Model):
    """Admin-controlled ISO-4217 currency registry used across ShopU."""
    code = models.CharField(max_length=3, unique=True)
    name = models.CharField(max_length=80)
    symbol = models.CharField(max_length=8, blank=True)
    decimal_places = models.PositiveSmallIntegerField(default=2)
    enabled = models.BooleanField(default=True)
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["code"]

    def save(self, *args, **kwargs):
        self.code = self.code.upper().strip()
        super().save(*args, **kwargs)
        if self.is_default:
            type(self).objects.exclude(pk=self.pk).filter(is_default=True).update(is_default=False)

    def __str__(self):
        return f"{self.code} — {self.name}"

class PaymentGatewayConfig(models.Model):
    provider = models.CharField(max_length=40, unique=True)
    enabled = models.BooleanField(default=False)
    priority = models.PositiveIntegerField(default=100)
    supported_currencies = models.JSONField(default=list, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["priority", "provider"]

    def __str__(self):
        return f"{self.provider} ({'on' if self.enabled else 'off'})"


class PayoutProviderConfig(models.Model):
    """Admin-controlled payout provider configuration.

    Credentials/secrets must remain in environment variables.
    This model only controls operational settings.
    """
    provider = models.CharField(max_length=40, unique=True)
    name = models.CharField(max_length=80)
    enabled = models.BooleanField(default=False)
    priority = models.PositiveIntegerField(default=100)
    supported_currencies = models.JSONField(default=list, blank=True)
    supported_countries = models.JSONField(default=list, blank=True)
    min_amount = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0"))],
    )
    max_amount = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("0"))],
    )
    metadata = models.JSONField(default=dict, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["priority", "provider"]

    def __str__(self):
        return f"{self.name} ({'on' if self.enabled else 'off'})"
