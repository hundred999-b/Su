import uuid

from django.conf import settings
from django.db import models


class SecurityProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="security_profile",
    )

    pin_enabled = models.BooleanField(default=False)
    pin_hash = models.CharField(max_length=255, blank=True)

    two_factor_enabled = models.BooleanField(default=False)

    recovery_enabled = models.BooleanField(default=True)

    failed_pin_attempts = models.PositiveIntegerField(default=0)
    pin_locked_until = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Security: {self.user.username}"


class RecoveryCode(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="security_recovery_codes",
    )

    code_hash = models.CharField(max_length=255)
    used = models.BooleanField(default=False)
    used_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Recovery code #{self.pk} for {self.user.username}"


class SecurityQuestion(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="security_questions",
    )

    question = models.CharField(max_length=255)
    answer_hash = models.CharField(max_length=255)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Security question for {self.user.username}"


class TrustedTelegram(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="trusted_telegrams",
    )

    telegram_user_id = models.BigIntegerField()
    username = models.CharField(max_length=255, blank=True)

    verified = models.BooleanField(default=False)
    verified_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "telegram_user_id"],
                name="unique_user_trusted_telegram",
            ),
        ]

    def __str__(self):
        return f"Trusted Telegram for {self.user.username}"


class SecurityOTP(models.Model):
    PURPOSE_PURCHASE = "purchase"
    PURPOSE_WITHDRAWAL = "withdrawal"
    PURPOSE_LOGIN = "login"
    PURPOSE_RECOVERY = "recovery"
    PURPOSE_SECURITY_CHANGE = "security_change"

    PURPOSE_CHOICES = [
        (PURPOSE_PURCHASE, "Purchase"),
        (PURPOSE_WITHDRAWAL, "Withdrawal"),
        (PURPOSE_LOGIN, "Login"),
        (PURPOSE_RECOVERY, "Recovery"),
        (PURPOSE_SECURITY_CHANGE, "Security change"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="security_otps",
    )

    purpose = models.CharField(max_length=40, choices=PURPOSE_CHOICES)
    code_hash = models.CharField(max_length=255)

    expires_at = models.DateTimeField()
    used = models.BooleanField(default=False)
    used_at = models.DateTimeField(null=True, blank=True)

    attempts = models.PositiveIntegerField(default=0)

    challenge_id = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
    )

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.purpose} OTP for {self.user.username}"


class SecurityEvent(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="security_events",
    )

    event_type = models.CharField(max_length=80)
    success = models.BooleanField(default=True)

    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)

    metadata = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.event_type} - {self.user.username}"
