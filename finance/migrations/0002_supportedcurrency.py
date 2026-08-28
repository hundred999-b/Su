from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("finance", "0001_initial")]
    operations = [
        migrations.CreateModel(
            name="SupportedCurrency",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("code", models.CharField(max_length=3, unique=True)),
                ("name", models.CharField(max_length=80)),
                ("symbol", models.CharField(blank=True, max_length=8)),
                ("decimal_places", models.PositiveSmallIntegerField(default=2)),
                ("enabled", models.BooleanField(default=True)),
                ("is_default", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"ordering": ["code"]},
        ),
    ]
