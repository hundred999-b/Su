from django.db import migrations


def seed(apps, schema_editor):
    Gateway = apps.get_model("finance", "PaymentGatewayConfig")
    Gateway.objects.get_or_create(provider="stripe", defaults={"priority": 10, "enabled": False, "supported_currencies": []})
    Gateway.objects.get_or_create(provider="paystack", defaults={"priority": 20, "enabled": False, "supported_currencies": []})


class Migration(migrations.Migration):
    dependencies = [("finance", "0005_seed_common_currencies")]
    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
