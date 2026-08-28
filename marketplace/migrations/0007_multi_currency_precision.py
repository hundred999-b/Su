from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("marketplace", "0006_order_idempotency")]
    operations = [
        migrations.AlterField(model_name="product", name="price", field=models.DecimalField(decimal_places=8, max_digits=24)),
        migrations.AlterField(model_name="listingversion", name="price", field=models.DecimalField(decimal_places=8, max_digits=24)),
        migrations.AlterField(model_name="order", name="amount", field=models.DecimalField(decimal_places=8, max_digits=24)),
    ]
