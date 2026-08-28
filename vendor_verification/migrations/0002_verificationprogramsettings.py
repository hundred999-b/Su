from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("vendor_verification", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="VerificationProgramSettings",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("singleton", models.BooleanField(default=True, editable=False, unique=True)),
                ("enabled", models.BooleanField(default=True)),
                ("require_identity", models.BooleanField(default=True)),
                ("require_business", models.BooleanField(default=False)),
                ("require_payment_history", models.BooleanField(default=False)),
                ("require_transaction_history", models.BooleanField(default=True)),
                ("minimum_completed_transactions", models.PositiveIntegerField(default=0)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
        ),
    ]
