from decimal import Decimal
from django.core.validators import MinValueValidator
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("giftcards", "0001_initial")]
    operations = [
        migrations.AlterField(model_name="giftcard", name="initial_amount", field=models.DecimalField(decimal_places=8, max_digits=24, validators=[MinValueValidator(Decimal("0.01"))])),
        migrations.AlterField(model_name="giftcard", name="remaining_amount", field=models.DecimalField(decimal_places=8, max_digits=24, validators=[MinValueValidator(Decimal("0"))])),
        migrations.AlterField(model_name="giftcardredemption", name="amount", field=models.DecimalField(decimal_places=8, max_digits=24, validators=[MinValueValidator(Decimal("0.01"))])),
    ]
