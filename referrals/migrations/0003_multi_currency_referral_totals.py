from django.db import migrations, models


def copy_totals(apps, schema_editor):
    Profile = apps.get_model("referrals", "ReferralProfile")
    for profile in Profile.objects.all():
        rewards = profile.rewards.all()
        totals = {}
        for reward in rewards:
            code = reward.currency.upper()
            totals[code] = str(__import__('decimal').Decimal(totals.get(code, "0")) + reward.amount)
        profile.total_earned_by_currency = totals
        profile.save(update_fields=["total_earned_by_currency"])


class Migration(migrations.Migration):
    dependencies = [("referrals", "0002_multi_currency_precision")]
    operations = [
        migrations.AddField(model_name="referralprofile", name="total_earned_by_currency", field=models.JSONField(blank=True, default=dict)),
        migrations.RunPython(copy_totals, migrations.RunPython.noop),
        migrations.RemoveField(model_name="referralprofile", name="total_earned"),
    ]
