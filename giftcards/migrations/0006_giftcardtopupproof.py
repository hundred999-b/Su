from django.db import migrations, models
class Migration(migrations.Migration):
    dependencies = [("giftcards", "0005_giftcardtopupsettings")]
    operations = [migrations.AddField(model_name="giftcardtopup", name="purchase_proof", field=models.TextField(blank=True))]
