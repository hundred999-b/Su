from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("escrow", "0005_alter_escrow_options")]
    operations = [
        migrations.AlterField(model_name="escrow", name="amount", field=models.DecimalField(decimal_places=8, max_digits=24)),
        migrations.AlterField(model_name="escrow", name="funded_cash_amount", field=models.DecimalField(decimal_places=8, default=0, max_digits=24)),
        migrations.AlterField(model_name="escrow", name="funded_gift_amount", field=models.DecimalField(decimal_places=8, default=0, max_digits=24)),
        migrations.AlterField(model_name="privateescrow", name="amount", field=models.DecimalField(decimal_places=8, max_digits=24)),
        migrations.AlterField(model_name="privateescrow", name="funded_cash_amount", field=models.DecimalField(decimal_places=8, default=0, max_digits=24)),
        migrations.AlterField(model_name="privateescrow", name="funded_gift_amount", field=models.DecimalField(decimal_places=8, default=0, max_digits=24)),
    ]
