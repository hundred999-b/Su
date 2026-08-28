from django.contrib.auth.models import User
from django.db import models


class Wallet(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="wallets",
    )

    currency = models.CharField(
        max_length=10,
        default="USD",
    )

    ledger_account = models.OneToOneField(
        "ledger.LedgerAccount",
        on_delete=models.PROTECT,
        related_name="wallet",
    )

    active = models.BooleanField(
        default=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "currency"],
                name="unique_user_wallet_currency",
            )
        ]

    def __str__(self):
        return f"{self.user.username} - {self.currency}"
