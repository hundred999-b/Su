from django.db import migrations, models
import django.db.models.deletion
from django.conf import settings
class Migration(migrations.Migration):
    dependencies=[('telegram_integration','0001_initial')]
    operations=[migrations.CreateModel(name='Notification',fields=[
        ('id',models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name='ID')),
        ('kind',models.CharField(max_length=80)),('title',models.CharField(max_length=160)),('message',models.TextField()),('read',models.BooleanField(default=False)),('created_at',models.DateTimeField(auto_now_add=True)),
        ('user',models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,related_name='notifications',to=settings.AUTH_USER_MODEL)),
    ])]
