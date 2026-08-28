from django.db import migrations, models
import django.db.models.deletion


def seed_steps(apps, schema_editor):
    Step = apps.get_model("vendor_verification", "VerificationStep")
    defaults = [
        ("identity", "Identity verification", "Confirm the vendor's identity.", True, 10, "document"),
        ("business", "Business verification", "Confirm business details where applicable.", False, 20, "document"),
        ("payment_history", "Payment history", "Review payment history for trust and fraud signals.", False, 30, "manual"),
        ("transaction_history", "Transaction history", "Review completed marketplace transaction history.", True, 40, "boolean"),
    ]
    for key, name, description, required, order, evidence_type in defaults:
        Step.objects.get_or_create(key=key, defaults={"name": name, "description": description, "required": required, "order": order, "evidence_type": evidence_type})

class Migration(migrations.Migration):
    dependencies = [("vendor_verification", "0002_verificationprogramsettings")]
    operations = [
        migrations.CreateModel(
            name="VerificationStep",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("key", models.SlugField(max_length=80, unique=True)),
                ("name", models.CharField(max_length=120)),
                ("description", models.TextField(blank=True)),
                ("enabled", models.BooleanField(default=True)),
                ("required", models.BooleanField(default=True)),
                ("order", models.PositiveIntegerField(default=0)),
                ("evidence_type", models.CharField(choices=[("manual", "Manual review"), ("boolean", "Boolean check"), ("document", "Document evidence"), ("text", "Text evidence")], default="manual", max_length=30)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"ordering": ["order", "name"]},
        ),
        migrations.CreateModel(
            name="VerificationStepResult",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("status", models.CharField(choices=[("pending", "Pending"), ("passed", "Passed"), ("failed", "Failed")], default="pending", max_length=20)),
                ("evidence", models.TextField(blank=True)),
                ("reviewed_at", models.DateTimeField(blank=True, null=True)),
                ("reviewer_note", models.TextField(blank=True)),
                ("reviewed_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="verification_step_reviews", to="auth.user")),
                ("step", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="results", to="vendor_verification.verificationstep")),
                ("verification", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="step_results", to="vendor_verification.vendorverification")),
            ],
            options={"ordering": ["step__order", "step__name"]},
        ),
        migrations.AddConstraint(
            model_name="verificationstepresult",
            constraint=models.UniqueConstraint(fields=("verification", "step"), name="unique_vendor_verification_step"),
        ),
        migrations.RunPython(seed_steps, migrations.RunPython.noop),
    ]
