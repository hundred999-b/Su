from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("referrals", "0001_initial")]
    operations = [
        migrations.AlterField(model_name="referralprofile", name="total_earned", field=models.DecimalField(decimal_places=8, default="0.00", max_digits=24)),
        migrations.AlterField(model_name="referralreward", name="base_amount", field=models.DecimalField(decimal_places=8, max_digits=24)),
        migrations.AlterField(model_name="referralreward", name="amount", field=models.DecimalField(decimal_places=8, max_digits=24)),
    ]
