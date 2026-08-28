from django.db import migrations, models
class Migration(migrations.Migration):
    dependencies=[('marketplace','0002_product_image')]
    operations=[
        migrations.AddField(model_name='product',name='category',field=models.CharField(blank=True,db_index=True,max_length=80)),
        migrations.AddField(model_name='product',name='updated_at',field=models.DateTimeField(auto_now=True)),
        migrations.AddField(model_name='order',name='paid_at',field=models.DateTimeField(blank=True,null=True)),
        migrations.AddField(model_name='order',name='delivered_at',field=models.DateTimeField(blank=True,null=True)),
        migrations.AddField(model_name='order',name='confirmation_deadline',field=models.DateTimeField(blank=True,null=True)),
        migrations.AddField(model_name='order',name='confirmed_at',field=models.DateTimeField(blank=True,null=True)),
        migrations.AlterField(model_name='order',name='status',field=models.CharField(choices=[('pending','Pending'),('paid','Paid'),('escrow','Escrow'),('delivered','Delivered'),('completed','Completed'),('refunded','Refunded'),('disputed','Disputed')],default='pending',max_length=20)),
    ]
