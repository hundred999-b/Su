from django.conf import settings
from django.db import migrations, models
import django.core.validators
import django.db.models.deletion
from decimal import Decimal

class Migration(migrations.Migration):
    dependencies = [("giftcards", "0003_giftcardpurchase")]
    operations = [
        migrations.CreateModel(
            name="GiftCardTopUp",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("brand", models.CharField(max_length=120)),
                ("code_encrypted", models.TextField()),
                ("code_hash", models.CharField(db_index=True, max_length=64, unique=True)),
                ("code_last4", models.CharField(blank=True, max_length=8)),
                ("claimed_amount", models.DecimalField(decimal_places=8, max_digits=24, validators=[django.core.validators.MinValueValidator(Decimal("0.01"))])),
                ("claimed_currency", models.CharField(max_length=10)),
                ("approved_amount", models.DecimalField(blank=True, decimal_places=8, max_digits=24, null=True, validators=[django.core.validators.MinValueValidator(Decimal("0.01"))])),
                ("approved_currency", models.CharField(blank=True, max_length=10)),
                ("country", models.CharField(blank=True, max_length=3)),
                ("status", models.CharField(choices=[("pending", "Pending"), ("approved", "Approved"), ("rejected", "Rejected"), ("needs_info", "Needs Info")], db_index=True, default="pending", max_length=20)),
                ("user_note", models.TextField(blank=True)),
                ("review_note", models.TextField(blank=True)),
                ("reviewed_at", models.DateTimeField(blank=True, null=True)),
                ("ledger_transaction_id", models.CharField(blank=True, max_length=64, null=True, unique=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("reviewed_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="gift_card_topups_reviewed", to=settings.AUTH_USER_MODEL)),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="gift_card_topups", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-created_at"]},
        ),
    ]
