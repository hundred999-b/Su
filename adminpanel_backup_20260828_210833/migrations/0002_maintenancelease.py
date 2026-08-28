from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [("adminpanel", "0001_initial")]
    operations = [
        migrations.CreateModel(
            name="MaintenanceLease",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("singleton", models.BooleanField(default=True, editable=False, unique=True)),
                ("locked_until", models.DateTimeField(blank=True, null=True)),
                ("last_started_at", models.DateTimeField(blank=True, null=True)),
                ("last_finished_at", models.DateTimeField(blank=True, null=True)),
                ("last_result", models.JSONField(blank=True, default=dict)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
        ),
    ]
