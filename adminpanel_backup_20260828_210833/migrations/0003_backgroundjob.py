from django.db import migrations, models


def backfill_escrow_jobs(apps, schema_editor):
    Job = apps.get_model("adminpanel", "BackgroundJob")
    Order = apps.get_model("marketplace", "Order")
    now = __import__("django.utils.timezone", fromlist=["now"]).now()
    for order in Order.objects.filter(status="delivered", confirmation_deadline__isnull=False):
        Job.objects.get_or_create(
            dedupe_key=f"escrow:auto-release:order:{order.pk}",
            defaults={
                "kind": "escrow.auto_release",
                "payload": {"order_id": order.pk},
                "run_after": order.confirmation_deadline,
            },
        )

class Migration(migrations.Migration):
    dependencies = [
        ("adminpanel", "0002_maintenancelease"),
        ("marketplace", "0003_shopu_marketplace"),
    ]
    operations = [
        migrations.CreateModel(
            name="BackgroundJob",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("kind", models.CharField(db_index=True, max_length=100)),
                ("dedupe_key", models.CharField(max_length=180, unique=True)),
                ("payload", models.JSONField(blank=True, default=dict)),
                ("result", models.JSONField(blank=True, default=dict)),
                ("status", models.CharField(choices=[("pending", "Pending"), ("running", "Running"), ("completed", "Completed"), ("failed", "Failed")], db_index=True, default="pending", max_length=20)),
                ("run_after", models.DateTimeField(db_index=True)),
                ("attempts", models.PositiveIntegerField(default=0)),
                ("max_attempts", models.PositiveIntegerField(default=5)),
                ("locked_until", models.DateTimeField(blank=True, null=True)),
                ("started_at", models.DateTimeField(blank=True, null=True)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                ("last_error", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"indexes": [models.Index(fields=["status", "run_after"], name="adminpanel_b_status_6d8d7e_idx"), models.Index(fields=["kind", "status"], name="adminpanel_b_kind_7f5b4b_idx")]},
        ),
        migrations.RunPython(backfill_escrow_jobs, migrations.RunPython.noop),
    ]
