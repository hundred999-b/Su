from decimal import Decimal
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import migrations, models
import django.db.models.deletion

def seed_settings(apps, schema_editor):
    apps.get_model("referrals", "ReferralProgramSettings").objects.get_or_create(
        pk=1, defaults={"enabled": True, "transactions_limit": 10, "commission_percent": Decimal("0.5000")}
    )

class Migration(migrations.Migration):
    initial = True
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("marketplace", "0006_order_idempotency"),
    ]
    operations = [
        migrations.CreateModel(
            name="ReferralProgramSettings",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("singleton", models.BooleanField(default=True, editable=False, unique=True)),
                ("enabled", models.BooleanField(default=True)),
                ("transactions_limit", models.PositiveIntegerField(default=10, validators=[MinValueValidator(1), MaxValueValidator(100)])),
                ("commission_percent", models.DecimalField(decimal_places=4, default=Decimal("0.5000"), max_digits=7, validators=[MinValueValidator(Decimal("0")), MaxValueValidator(Decimal("100"))])),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
        ),
        migrations.CreateModel(
            name="ReferralProfile",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("code", models.CharField(db_index=True, max_length=32, unique=True)),
                ("attributed_at", models.DateTimeField(blank=True, null=True)),
                ("eligible_transactions_count", models.PositiveIntegerField(default=0)),
                ("total_earned", models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=18)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("referred_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="referred_users", to=settings.AUTH_USER_MODEL)),
                ("user", models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name="referral_profile", to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name="ReferralReward",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("sequence", models.PositiveIntegerField()),
                ("base_amount", models.DecimalField(decimal_places=2, max_digits=18)),
                ("commission_percent", models.DecimalField(decimal_places=4, max_digits=7)),
                ("amount", models.DecimalField(decimal_places=2, max_digits=18)),
                ("currency", models.CharField(max_length=10)),
                ("ledger_transaction_id", models.CharField(max_length=64, unique=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("order", models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name="referral_reward", to="marketplace.order")),
                ("referral", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="rewards", to="referrals.referralprofile")),
                ("referred_user", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="referral_rewards_generated", to=settings.AUTH_USER_MODEL)),
                ("referrer", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="referral_rewards", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.AddConstraint(
            model_name="referralreward",
            constraint=models.UniqueConstraint(fields=("referral", "sequence"), name="unique_referral_reward_sequence"),
        ),
        migrations.RunPython(seed_settings, migrations.RunPython.noop),
    ]
