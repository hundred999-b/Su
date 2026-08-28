from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies=[("escrow","0002_private_escrow")]
    operations=[
        migrations.AddField(model_name="escrow",name="funding_transaction_id",field=models.CharField(blank=True,max_length=64)),
        migrations.AddField(model_name="escrow",name="funded_cash_amount",field=models.DecimalField(decimal_places=2,default=0,max_digits=18)),
        migrations.AddField(model_name="escrow",name="funded_gift_amount",field=models.DecimalField(decimal_places=2,default=0,max_digits=18)),
    ]
