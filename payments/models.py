from django.conf import settings
from django.db import models


class Payment(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="payments")
    PENDING = "pending"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    REFUNDED = "refunded"

    STATUS_CHOICES = [
        (PENDING, "Pending"),
        (SUCCEEDED, "Succeeded"),
        (FAILED, "Failed"),
        (REFUNDED, "Refunded"),
    ]

    provider = models.CharField(
        max_length=80,
    )

    provider_reference = models.CharField(
        max_length=160,
        unique=True,
    )

    amount = models.DecimalField(
        max_digits=24,
        decimal_places=8,
    )

    currency = models.CharField(
        max_length=10,
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=PENDING,
    )

    authorization_url = models.URLField(blank=True)
    access_code = models.CharField(max_length=160, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    idempotency_key = models.CharField(
        max_length=160,
        unique=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    def __str__(self):
        return f"{self.provider}:{self.provider_reference}"
