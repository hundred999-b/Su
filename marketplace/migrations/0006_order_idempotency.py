from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("marketplace", "0005_alter_product_condition_alter_product_description"),
    ]

    operations = [
        migrations.AddField(
            model_name="order",
            name="idempotency_key",
            field=models.CharField(blank=True, db_index=True, max_length=120, null=True, unique=True),
        ),
    ]
