from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("crypto", "0002_nowpayments")]
    operations = [migrations.AlterField(model_name="cryptodeposit", name="asset", field=models.CharField(max_length=30)), migrations.AlterField(model_name="cryptowithdrawal", name="asset", field=models.CharField(max_length=30))]
