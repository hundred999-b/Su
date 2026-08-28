from django.db import migrations, models
class Migration(migrations.Migration):
    dependencies=[('reviews','0001_initial')]
    operations=[migrations.AddField(model_name='review',name='visible',field=models.BooleanField(default=True)),migrations.AddField(model_name='review',name='moderation_note',field=models.CharField(blank=True,max_length=255))]
