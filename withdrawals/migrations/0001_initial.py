from django.conf import settings
from django.db import migrations, models
from django.core.validators import MinValueValidator
import decimal
class Migration(migrations.Migration):
    initial=True
    dependencies=[('auth','0012_alter_user_first_name_max_length')]
    operations=[migrations.CreateModel(name='WithdrawalRequest',fields=[
        ('id',models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name='ID')),
        ('amount',models.DecimalField(decimal_places=2,max_digits=18,validators=[MinValueValidator(decimal.Decimal('0.01'))])),
        ('fee',models.DecimalField(decimal_places=2,default=decimal.Decimal('0'),max_digits=18,validators=[MinValueValidator(decimal.Decimal('0'))])),
        ('currency',models.CharField(default='USD',max_length=10)),('method',models.CharField(max_length=40)),
        ('destination_reference',models.CharField(max_length=255)),('status',models.CharField(choices=[('pending','Pending'),('processing','Processing'),('completed','Completed'),('failed','Failed'),('cancelled','Cancelled')],default='pending',max_length=20)),
        ('provider_reference',models.CharField(blank=True,max_length=160)),('failure_reason',models.TextField(blank=True)),('created_at',models.DateTimeField(auto_now_add=True)),('updated_at',models.DateTimeField(auto_now=True)),
        ('user',models.ForeignKey(on_delete=models.deletion.PROTECT,related_name='withdrawal_requests',to=settings.AUTH_USER_MODEL)),
    ])]
