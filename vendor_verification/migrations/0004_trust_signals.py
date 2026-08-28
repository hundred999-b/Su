from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("vendor_verification", "0003_dynamic_verification_steps"),
        ("marketplace", "0007_multi_currency_precision"),
        ("support", "0002_support_order_and_message_limits"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="vendorverification",
            name="trusted_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="vendor_trust_promotions",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(model_name="vendorverification", name="trusted_at", field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(model_name="vendorverification", name="trusted_reason", field=models.TextField(blank=True)),
        migrations.AddField(model_name="vendorverification", name="caution_override", field=models.BooleanField(blank=True, default=None, null=True)),
        migrations.AddField(model_name="vendorverification", name="caution_note", field=models.TextField(blank=True)),
        migrations.CreateModel(
            name="VendorComplaint",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("category", models.CharField(default="other", max_length=60)),
                ("severity", models.CharField(choices=[("low", "Low"), ("medium", "Medium"), ("high", "High"), ("critical", "Critical")], default="medium", max_length=20)),
                ("status", models.CharField(choices=[("open", "Open"), ("substantiated", "Substantiated"), ("dismissed", "Dismissed"), ("resolved", "Resolved")], db_index=True, default="open", max_length=20)),
                ("description", models.TextField(max_length=10000)),
                ("resolution_note", models.TextField(blank=True, max_length=5000)),
                ("resolved_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("order", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="vendor_complaints", to="marketplace.order")),
                ("reporter", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="vendor_complaints_reported", to=settings.AUTH_USER_MODEL)),
                ("reviewed_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="vendor_complaints_reviewed", to=settings.AUTH_USER_MODEL)),
                ("seller", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="vendor_complaints", to=settings.AUTH_USER_MODEL)),
                ("ticket", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="vendor_complaints", to="support.ticket")),
            ],
            options={"ordering": ["-created_at"], "indexes": [models.Index(fields=["seller", "status"], name="vendor_ver_seller__b1a0d7_idx"), models.Index(fields=["seller", "severity"], name="vendor_ver_seller__c9e7ef_idx")]},
        ),
        migrations.CreateModel(
            name="VendorTrustSettings",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("singleton", models.BooleanField(default=True, editable=False, unique=True)),
                ("caution_dispute_threshold", models.PositiveIntegerField(default=3)),
                ("caution_complaint_threshold", models.PositiveIntegerField(default=2)),
                ("caution_dispute_rate_percent", models.PositiveIntegerField(default=20)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
        ),
    ]
