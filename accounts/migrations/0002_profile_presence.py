from django.db import migrations, models
class Migration(migrations.Migration):
    dependencies=[('accounts','0001_initial')]
    operations=[
        migrations.AddField(model_name='profile',name='telegram_id',field=models.CharField(blank=True,db_index=True,max_length=64)),
        migrations.AddField(model_name='profile',name='last_seen_at',field=models.DateTimeField(blank=True,null=True)),
        migrations.AddField(model_name='profile',name='presence_enabled',field=models.BooleanField(default=True)),
        migrations.AddField(model_name='profile',name='suspended',field=models.BooleanField(default=False)),
    ]
