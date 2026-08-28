from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("finance", "0002_supportedcurrency")]
    operations = [
        migrations.AlterField(model_name="cryptoassetconfig", name="asset", field=models.CharField(max_length=30, unique=True)),
    ]
