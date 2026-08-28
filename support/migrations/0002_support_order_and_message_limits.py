from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):
    dependencies = [('support','0001_initial'), ('marketplace','0007_multi_currency_precision')]
    operations = [
        migrations.AddField(model_name='ticket', name='related_order', field=models.ForeignKey(blank=True, help_text='Optional ShopU marketplace order this ticket concerns.', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='support_tickets', to='marketplace.order')),
        migrations.AlterField(model_name='ticketmessage', name='content', field=models.TextField(max_length=5000)),
    ]
