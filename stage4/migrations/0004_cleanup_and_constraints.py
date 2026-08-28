from django.db import migrations, models


def deduplicate_acceptances(apps, schema_editor):
    Acceptance = apps.get_model("stage4", "TermsAcceptance")
    seen = set()
    duplicates = []
    for row in Acceptance.objects.order_by("user_id", "terms_id", "purpose", "accepted_at", "id"):
        key = (row.user_id, row.terms_id, row.purpose)
        if key in seen:
            duplicates.append(row.id)
        else:
            seen.add(key)
    if duplicates:
        Acceptance.objects.filter(id__in=duplicates).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("stage4", "0003_alter_termsdocument_kind"),
    ]

    operations = [
        migrations.DeleteModel(name="VendorVerification"),
        migrations.RunPython(deduplicate_acceptances, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name="termsacceptance",
            constraint=models.UniqueConstraint(
                fields=("user", "terms", "purpose"),
                name="stage4_termsacceptance_unique",
            ),
        ),
    ]
