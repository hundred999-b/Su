from django.conf import settings
from django.db import migrations, models
from django.core.validators import MinValueValidator
import decimal
class Migration(migrations.Migration):
    initial=True
    dependencies=[('auth','0012_alter_user_first_name_max_length')]
    operations=[
        migrations.CreateModel(name='GiftCard', fields=[
            ('id',models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name='ID')),
            ('code',models.CharField(db_index=True,max_length=64,unique=True)),
            ('currency',models.CharField(default='USD',max_length=10)),
            ('initial_amount',models.DecimalField(decimal_places=2,max_digits=18,validators=[MinValueValidator(decimal.Decimal('0.01'))])),
            ('remaining_amount',models.DecimalField(decimal_places=2,max_digits=18,validators=[MinValueValidator(decimal.Decimal('0'))])),
            ('status',models.CharField(choices=[('active','Active'),('disabled','Disabled'),('exhausted','Exhausted'),('expired','Expired')],default='active',max_length=20)),
            ('expires_at',models.DateTimeField(blank=True,null=True)),('created_at',models.DateTimeField(auto_now_add=True))]),
        migrations.CreateModel(name='GiftCardRedemption', fields=[
            ('id',models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name='ID')),
            ('amount',models.DecimalField(decimal_places=2,max_digits=18,validators=[MinValueValidator(decimal.Decimal('0.01'))])),
            ('created_at',models.DateTimeField(auto_now_add=True)),
            ('gift_card',models.ForeignKey(on_delete=models.deletion.PROTECT,related_name='redemptions',to='giftcards.giftcard')),
            ('user',models.ForeignKey(on_delete=models.deletion.PROTECT,related_name='gift_card_redemptions',to=settings.AUTH_USER_MODEL)),
        ]),
    ]
