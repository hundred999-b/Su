from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("stage4", "0004_cleanup_and_constraints")]
    operations = [
        migrations.AlterField(model_name="listingversion", name="price", field=models.DecimalField(decimal_places=8, max_digits=24)),
        migrations.AlterField(model_name="orderlistingsnapshot", name="price", field=models.DecimalField(decimal_places=8, max_digits=24)),
    ]
