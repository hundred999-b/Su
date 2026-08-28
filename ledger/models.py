from django.core.validators import MinValueValidator
from django.db import models


class LedgerAccount(models.Model):
    ASSET = "asset"
    LIABILITY = "liability"
    REVENUE = "revenue"
    EXPENSE = "expense"
    EQUITY = "equity"

    TYPES = [
        (ASSET, "Asset"),
        (LIABILITY, "Liability"),
        (REVENUE, "Revenue"),
        (EXPENSE, "Expense"),
        (EQUITY, "Equity"),
    ]

    name = models.CharField(max_length=120)

    account_type = models.CharField(
        max_length=20,
        choices=TYPES,
    )

    currency = models.CharField(
        max_length=10,
        default="USD",
    )

    active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("name", "currency"),
                name="unique_ledger_account_name_currency",
            )
        ]

    def __str__(self):
        return f"{self.name} [{self.currency}]"


class LedgerTransaction(models.Model):
    transaction_id = models.CharField(
        max_length=64,
        unique=True,
    )

    description = models.CharField(
        max_length=255,
    )

    reference = models.CharField(
        max_length=120,
        blank=True,
    )

    # Durable idempotency key for financial operations.
    # NULL/blank means the caller does not require idempotency.
    idempotency_key = models.CharField(
        max_length=160,
        unique=True,
        null=True,
        blank=True,
        db_index=True,
    )

    metadata = models.JSONField(
        default=dict,
        blank=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    def __str__(self):
        return self.transaction_id


class LedgerEntry(models.Model):
    DEBIT = "debit"
    CREDIT = "credit"

    DIRECTIONS = [
        (DEBIT, "Debit"),
        (CREDIT, "Credit"),
    ]

    transaction = models.ForeignKey(
        LedgerTransaction,
        on_delete=models.PROTECT,
        related_name="entries",
    )

    account = models.ForeignKey(
        LedgerAccount,
        on_delete=models.PROTECT,
        related_name="entries",
    )

    amount = models.DecimalField(
        max_digits=24,
        decimal_places=8,
        validators=[MinValueValidator(0)],
    )

    direction = models.CharField(
        max_length=6,
        choices=DIRECTIONS,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(amount__gt=0),
                name="ledger_entry_positive",
            )
        ]


from .wallet_models import Wallet
