from decimal import Decimal
import secrets
import string
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models

class ReferralProgramSettings(models.Model):
    singleton = models.BooleanField(default=True, unique=True, editable=False)
    enabled = models.BooleanField(default=True)
    transactions_limit = models.PositiveIntegerField(default=10, validators=[MinValueValidator(1), MaxValueValidator(100)])
    commission_percent = models.DecimalField(
        max_digits=7, decimal_places=4, default=Decimal("0.5000"),
        validators=[MinValueValidator(Decimal("0")), MaxValueValidator(Decimal("100"))],
    )
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def get_solo(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def __str__(self):
        return "ShopU Referral Program Settings"

class ReferralProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="referral_profile")
    code = models.CharField(max_length=32, unique=True, db_index=True)
    referred_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="referred_users")
    attributed_at = models.DateTimeField(null=True, blank=True)
    eligible_transactions_count = models.PositiveIntegerField(default=0)
    total_earned_by_currency = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    @staticmethod
    def generate_code():
        alphabet = string.ascii_letters + string.digits
        return "SU" + "".join(secrets.choice(alphabet) for _ in range(10))

    def save(self, *args, **kwargs):
        if not self.code:
            for _ in range(10):
                candidate = self.generate_code()
                if not type(self).objects.filter(code=candidate).exists():
                    self.code = candidate
                    break
            if not self.code:
                raise RuntimeError("Unable to generate a unique referral code")
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.user.username} → {self.code}"

class ReferralReward(models.Model):
    referral = models.ForeignKey(ReferralProfile, on_delete=models.PROTECT, related_name="rewards")
    referrer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="referral_rewards")
    referred_user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="referral_rewards_generated")
    order = models.OneToOneField("marketplace.Order", on_delete=models.PROTECT, related_name="referral_reward")
    sequence = models.PositiveIntegerField()
    base_amount = models.DecimalField(max_digits=24, decimal_places=8)
    commission_percent = models.DecimalField(max_digits=7, decimal_places=4)
    amount = models.DecimalField(max_digits=24, decimal_places=8)
    currency = models.CharField(max_length=10)
    ledger_transaction_id = models.CharField(max_length=64, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=("referral", "sequence"), name="unique_referral_reward_sequence")]
        ordering = ["-created_at"]

    def __str__(self):
        return f"Referral reward #{self.pk} - order {self.order_id}"
