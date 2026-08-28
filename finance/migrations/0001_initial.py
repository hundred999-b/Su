from django.db import migrations, models
from django.core.validators import MinValueValidator, MaxValueValidator
import decimal

class Migration(migrations.Migration):
    initial = True
    dependencies = []
    operations = [
        migrations.CreateModel(
            name='FinanceSettings',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('singleton', models.BooleanField(default=True, editable=False, unique=True)),
                ('default_currency', models.CharField(default='USD', max_length=10)),
                ('escrow_auto_release_hours', models.PositiveIntegerField(default=6)),
                ('min_deposit', models.DecimalField(decimal_places=2, default=decimal.Decimal('1.00'), max_digits=18, validators=[MinValueValidator(decimal.Decimal('0'))])),
                ('max_deposit', models.DecimalField(blank=True, decimal_places=2, max_digits=18, null=True, validators=[MinValueValidator(decimal.Decimal('0'))])),
                ('min_withdrawal', models.DecimalField(decimal_places=2, default=decimal.Decimal('10.00'), max_digits=18, validators=[MinValueValidator(decimal.Decimal('0'))])),
                ('max_withdrawal', models.DecimalField(blank=True, decimal_places=2, max_digits=18, null=True, validators=[MinValueValidator(decimal.Decimal('0'))])),
                ('withdrawal_fee', models.DecimalField(decimal_places=2, default=decimal.Decimal('0.00'), max_digits=18, validators=[MinValueValidator(decimal.Decimal('0'))])),
                ('gift_cards_enabled', models.BooleanField(default=True)),
                ('crypto_enabled', models.BooleanField(default=False)),
                ('bank_transfer_enabled', models.BooleanField(default=True)),
                ('card_enabled', models.BooleanField(default=False)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
        ),
        migrations.CreateModel(
            name='PaymentMethodConfig',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('key', models.CharField(max_length=40, unique=True)),
                ('name', models.CharField(max_length=80)),
                ('enabled', models.BooleanField(default=False)),
                ('display_order', models.PositiveIntegerField(default=0)),
                ('metadata', models.JSONField(blank=True, default=dict)),
            ],
            options={'ordering': ['display_order', 'name']},
        ),
        migrations.CreateModel(
            name='CryptoAssetConfig',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('asset', models.CharField(choices=[('USDT','USDT'),('BTC','BTC'),('ETH','ETH'),('LTC','LTC'),('SOL','SOL'),('XMR','XMR')], max_length=10, unique=True)),
                ('enabled', models.BooleanField(default=False)),
                ('network', models.CharField(blank=True, max_length=40)),
                ('min_deposit', models.DecimalField(decimal_places=12, default=decimal.Decimal('0'), max_digits=24, validators=[MinValueValidator(decimal.Decimal('0'))])),
                ('min_withdrawal', models.DecimalField(decimal_places=12, default=decimal.Decimal('0'), max_digits=24, validators=[MinValueValidator(decimal.Decimal('0'))])),
                ('confirmation_count', models.PositiveIntegerField(default=1)),
                ('withdrawal_fee', models.DecimalField(decimal_places=12, default=decimal.Decimal('0'), max_digits=24, validators=[MinValueValidator(decimal.Decimal('0'))])),
            ],
        ),
        migrations.CreateModel(
            name='CommissionRule',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100, unique=True)),
                ('fee_type', models.CharField(choices=[('marketplace','Marketplace'),('escrow','Escrow'),('payment','Payment')], max_length=20)),
                ('percentage', models.DecimalField(decimal_places=4, default=decimal.Decimal('0'), max_digits=7, validators=[MinValueValidator(decimal.Decimal('0')), MaxValueValidator(decimal.Decimal('100'))])),
                ('fixed_amount', models.DecimalField(decimal_places=2, default=decimal.Decimal('0'), max_digits=18, validators=[MinValueValidator(decimal.Decimal('0'))])),
                ('currency', models.CharField(default='USD', max_length=10)),
                ('enabled', models.BooleanField(default=True)),
            ],
        ),
        migrations.RunPython(lambda apps, schema_editor: [
            apps.get_model('finance','PaymentMethodConfig').objects.get_or_create(key=k, defaults={'name':n,'enabled':e,'display_order':i})
            for i,(k,n,e) in enumerate([('bank_transfer','Bank Transfer',True),('card','Card',False),('gift_card','Gift Card',True),('crypto','Crypto',False)])
        ], migrations.RunPython.noop),
        migrations.RunPython(lambda apps, schema_editor: [
            apps.get_model('finance','CryptoAssetConfig').objects.get_or_create(asset=a)
            for a in ('USDT','BTC','ETH','LTC','SOL','XMR')
        ], migrations.RunPython.noop),
        migrations.RunPython(lambda apps, schema_editor: [
            apps.get_model('finance','CommissionRule').objects.get_or_create(name='Marketplace Commission', fee_type='marketplace', percentage=0),
            apps.get_model('finance','CommissionRule').objects.get_or_create(name='Escrow Commission', fee_type='escrow', percentage=0),
            apps.get_model('finance','CommissionRule').objects.get_or_create(name='Payment Fee', fee_type='payment', percentage=0),
        ], migrations.RunPython.noop),
    ]
