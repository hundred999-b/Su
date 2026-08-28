from django.conf import settings
from django.db import migrations, models
class Migration(migrations.Migration):
    initial=True
    dependencies=[('auth','0012_alter_user_first_name_max_length')]
    operations=[migrations.CreateModel(name='BankTransfer',fields=[('id',models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name='ID')),('amount',models.DecimalField(decimal_places=2,max_digits=18)),('currency',models.CharField(default='USD',max_length=10)),('reference',models.CharField(max_length=160,unique=True)),('provider_reference',models.CharField(blank=True,max_length=160)),('status',models.CharField(choices=[('pending','Pending'),('confirmed','Confirmed'),('failed','Failed'),('expired','Expired')],default='pending',max_length=20)),('created_at',models.DateTimeField(auto_now_add=True)),('confirmed_at',models.DateTimeField(blank=True,null=True)),('user',models.ForeignKey(on_delete=models.deletion.PROTECT,related_name='bank_transfers',to=settings.AUTH_USER_MODEL))])]
