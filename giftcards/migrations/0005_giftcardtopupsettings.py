from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [("giftcards", "0004_giftcardtopup")]
    operations = [
        migrations.CreateModel(
            name="GiftCardTopUpSettings",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("singleton", models.BooleanField(default=True, editable=False, unique=True)),
                ("enabled", models.BooleanField(default=True)),
                ("manual_review_required", models.BooleanField(default=True)),
                ("minimum_amount", models.DecimalField(decimal_places=8, default=1, max_digits=24)),
                ("maximum_amount", models.DecimalField(blank=True, decimal_places=8, max_digits=24, null=True)),
                ("require_purchase_proof", models.BooleanField(default=False)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
        ),
    ]
