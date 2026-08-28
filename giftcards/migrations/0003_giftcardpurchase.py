from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
from django.core.validators import MinValueValidator
from decimal import Decimal


class Migration(migrations.Migration):
    dependencies = [("giftcards", "0002_multi_currency_precision"), ("payments", "0004_multi_currency_precision")]
    operations = [
        migrations.CreateModel(
            name="GiftCardPurchase",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("amount", models.DecimalField(decimal_places=8, max_digits=24, validators=[MinValueValidator(Decimal("0.01"))])),
                ("currency", models.CharField(max_length=10)),
                ("recipient_email", models.EmailField(blank=True, max_length=254)),
                ("status", models.CharField(choices=[("pending", "Pending"), ("paid", "Paid"), ("failed", "Failed"), ("cancelled", "Cancelled")], default="pending", max_length=20)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("paid_at", models.DateTimeField(blank=True, null=True)),
                ("buyer", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="gift_card_purchases", to=settings.AUTH_USER_MODEL)),
                ("gift_card", models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name="purchase", to="giftcards.giftcard")),
                ("payment", models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name="gift_card_purchase", to="payments.payment")),
            ],
        ),
    ]
