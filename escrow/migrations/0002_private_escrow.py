import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models
class Migration(migrations.Migration):
    dependencies=[('escrow','0001_initial'),('auth','0001_initial')]
    operations=[migrations.CreateModel(name='PrivateEscrow',fields=[
        ('id',models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name='ID')),
        ('escrow_id',models.CharField(db_index=True,max_length=20,unique=True)),
        ('title',models.CharField(max_length=200)),('description',models.TextField(blank=True)),
        ('amount',models.DecimalField(decimal_places=2,max_digits=18)),('currency',models.CharField(default='USD',max_length=10)),
        ('status',models.CharField(choices=[('created','Created'),('funded','Funded'),('delivered','Delivered'),('released','Released'),('refunded','Refunded'),('disputed','Disputed'),('cancelled','Cancelled')],default='created',max_length=20)),
        ('created_at',models.DateTimeField(auto_now_add=True)),('funded_at',models.DateTimeField(blank=True,null=True)),('delivered_at',models.DateTimeField(blank=True,null=True)),('deadline',models.DateTimeField(blank=True,null=True)),('released_at',models.DateTimeField(blank=True,null=True)),
        ('buyer',models.ForeignKey(blank=True,null=True,on_delete=django.db.models.deletion.PROTECT,related_name='private_escrows_as_buyer',to=settings.AUTH_USER_MODEL)),
        ('seller',models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,related_name='private_escrows_as_seller',to=settings.AUTH_USER_MODEL)),
    ])]
