from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("crypto", "0001_initial")]
    operations = [
        migrations.AlterField(model_name="cryptodeposit", name="tx_hash", field=models.CharField(blank=True, max_length=255, null=True, unique=True)),
        migrations.AddField(model_name="cryptodeposit", name="provider", field=models.CharField(default="manual", max_length=40)),
        migrations.AddField(model_name="cryptodeposit", name="provider_payment_id", field=models.CharField(blank=True, max_length=120, null=True, unique=True)),
        migrations.AddField(model_name="cryptodeposit", name="price_currency", field=models.CharField(default="USD", max_length=10)),
        migrations.AddField(model_name="cryptodeposit", name="pay_currency", field=models.CharField(blank=True, max_length=30)),
        migrations.AddField(model_name="cryptodeposit", name="pay_amount", field=models.DecimalField(blank=True, decimal_places=12, max_digits=24, null=True)),
        migrations.AddField(model_name="cryptodeposit", name="payment_url", field=models.URLField(blank=True)),
        migrations.AddField(model_name="cryptodeposit", name="metadata", field=models.JSONField(blank=True, default=dict)),
    ]
