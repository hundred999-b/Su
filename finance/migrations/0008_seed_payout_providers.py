from django.db import migrations


def seed_payout_providers(apps, schema_editor):
    PayoutProviderConfig = apps.get_model(
        "finance",
        "PayoutProviderConfig",
    )

    providers = [
        ("paystack", "Paystack", 10),
        ("stripe_connect", "Stripe Connect", 20),
        ("airwallex", "Airwallex", 30),
        ("mangopay", "Mangopay", 40),
        ("nowpayments", "NOWPayments", 50),
    ]

    for provider, name, priority in providers:
        PayoutProviderConfig.objects.get_or_create(
            provider=provider,
            defaults={
                "name": name,
                "enabled": False,
                "priority": priority,
                "supported_currencies": [],
            },
        )


class Migration(migrations.Migration):

    dependencies = [
        ("finance", "0007_payoutproviderconfig"),
    ]

    operations = [
        migrations.RunPython(
            seed_payout_providers,
            migrations.RunPython.noop,
        ),
    ]
