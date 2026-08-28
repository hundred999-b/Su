from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("finance", "0003_unrestrict_crypto_assets")]
    operations = [
        migrations.CreateModel(
            name="PaymentGatewayConfig",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("provider", models.CharField(max_length=40, unique=True)),
                ("enabled", models.BooleanField(default=False)),
                ("priority", models.PositiveIntegerField(default=100)),
                ("supported_currencies", models.JSONField(blank=True, default=list)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"ordering": ["priority", "provider"]},
        ),
    ]
