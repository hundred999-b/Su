from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [('accounts','0002_profile_presence')]
    operations = [migrations.AddField(model_name='profile', name='profile_image', field=models.ImageField(blank=True, null=True, upload_to='profiles/'))]
