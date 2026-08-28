from decimal import Decimal
from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models


class WithdrawalRequest(models.Model):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

    STATUS_CHOICES = [
        (PENDING, "Pending"),
        (PROCESSING, "Processing"),
        (COMPLETED, "Completed"),
        (FAILED, "Failed"),
        (CANCELLED, "Cancelled"),
    ]

    PROVIDER_PAYSTACK = "paystack"
    PROVIDER_STRIPE_CONNECT = "stripe_connect"
    PROVIDER_AIRWALLEX = "airwallex"
    PROVIDER_MANGOPAY = "mangopay"
    PROVIDER_NOWPAYMENTS = "nowpayments"

    PROVIDER_CHOICES = [
        (PROVIDER_PAYSTACK, "Paystack"),
        (PROVIDER_STRIPE_CONNECT, "Stripe Connect"),
        (PROVIDER_AIRWALLEX, "Airwallex"),
        (PROVIDER_MANGOPAY, "Mangopay"),
        (PROVIDER_NOWPAYMENTS, "NOWPayments"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="withdrawal_requests",
    )

    amount = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )

    fee = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        default=Decimal("0"),
        validators=[MinValueValidator(Decimal("0"))],
    )

    currency = models.CharField(max_length=10, default="USD")
    method = models.CharField(max_length=40, default="bank")

    provider = models.CharField(
        max_length=40,
        choices=PROVIDER_CHOICES,
        blank=True,
    )

    destination_reference = models.CharField(
        max_length=255,
    )

    provider_recipient = models.CharField(
        max_length=255,
        blank=True,
    )

    provider_reference = models.CharField(
        max_length=160,
        blank=True,
        db_index=True,
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=PENDING,
        db_index=True,
    )

    failure_reason = models.TextField(blank=True)

    provider_metadata = models.JSONField(
        default=dict,
        blank=True,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self):
        return (
            f"Withdrawal #{self.pk} "
            f"{self.amount} {self.currency} {self.status}"
        )
