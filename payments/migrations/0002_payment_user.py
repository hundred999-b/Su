from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("payments", "0001_initial")]
    operations = [
        migrations.AddField(
            model_name="payment",
            name="user",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="payments", to=settings.AUTH_USER_MODEL),
        ),
    ]
