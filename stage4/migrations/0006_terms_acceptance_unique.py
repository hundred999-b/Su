from django.db import migrations, models


def dedupe(apps, schema_editor):
    TermsAcceptance = apps.get_model("stage4", "TermsAcceptance")
    seen = set()
    for obj in TermsAcceptance.objects.order_by("id"):
        key = (obj.user_id, obj.terms_id, obj.purpose)
        if key in seen:
            obj.delete()
        else:
            seen.add(key)


class Migration(migrations.Migration):
    dependencies = [("stage4", "0005_multi_currency_precision")]
    operations = [
        migrations.RunPython(dedupe, migrations.RunPython.noop),
        migrations.AddConstraint(model_name="termsacceptance", constraint=models.UniqueConstraint(fields=("user", "terms", "purpose"), name="stage4_terms_acceptance_unique")),
    ]
