from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("payments", "0003_payment_gateway_fields")]
    operations = [migrations.AlterField(model_name="payment", name="amount", field=models.DecimalField(decimal_places=8, max_digits=24))]
