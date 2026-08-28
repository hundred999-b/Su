from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("payments", "0002_payment_user"),
    ]

    operations = [
        migrations.AddField(
            model_name="payment",
            name="authorization_url",
            field=models.URLField(blank=True),
        ),
        migrations.AddField(
            model_name="payment",
            name="access_code",
            field=models.CharField(blank=True, max_length=160),
        ),
        migrations.AddField(
            model_name="payment",
            name="metadata",
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
