from django.db import migrations, models
import django.db.models.deletion
from django.utils import timezone


DEFAULT_POLICY = """By publishing a listing, the seller confirms that the information is accurate and complete to the best of their knowledge, including material defects, limitations, missing parts/accessories, condition, compatibility and other facts a reasonable buyer would need to make an informed decision. The seller agrees to ShopU marketplace rules and applicable fees. Misleading, fraudulent or materially incomplete listings may be subject to moderation, refunds, disputes or account action."""


def seed_policy(apps, schema_editor):
    Policy = apps.get_model("marketplace", "ListingPolicy")
    Policy.objects.get_or_create(
        key="seller_listing_terms",
        defaults={"version": 1, "title": "Seller Listing Terms", "content": DEFAULT_POLICY, "active": True},
    )


class Migration(migrations.Migration):
    dependencies = [("marketplace", "0003_shopu_marketplace")]

    operations = [
        migrations.CreateModel(
            name="ListingPolicy",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("key", models.CharField(default="seller_listing_terms", max_length=80, unique=True)),
                ("version", models.PositiveIntegerField(default=1)),
                ("title", models.CharField(default="Seller Listing Terms", max_length=200)),
                ("content", models.TextField()),
                ("active", models.BooleanField(default=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"ordering": ["-version"]},
        ),
        migrations.AddField(model_name="product", name="condition", field=models.CharField(blank=True, default="", max_length=80)),
        migrations.AddField(model_name="product", name="specifications", field=models.JSONField(blank=True, default=dict)),
        migrations.AddField(model_name="product", name="seller_terms", field=models.TextField(blank=True)),
        migrations.AddField(model_name="product", name="disclosure_acknowledged", field=models.BooleanField(default=False)),
        migrations.AddField(model_name="product", name="fee_acknowledged", field=models.BooleanField(default=False)),
        migrations.AddField(model_name="product", name="listing_policy_version", field=models.PositiveIntegerField(default=1)),
        migrations.AddField(model_name="product", name="listing_policy_content", field=models.TextField(blank=True)),
        migrations.AddField(model_name="product", name="published_at", field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(model_name="product", name="version", field=models.PositiveIntegerField(default=1)),
        migrations.CreateModel(
            name="ListingVersion",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("version", models.PositiveIntegerField()),
                ("title", models.CharField(max_length=200)),
                ("description", models.TextField()),
                ("category", models.CharField(blank=True, max_length=80)),
                ("condition", models.CharField(blank=True, max_length=80)),
                ("specifications", models.JSONField(blank=True, default=dict)),
                ("seller_terms", models.TextField(blank=True)),
                ("price", models.DecimalField(decimal_places=2, max_digits=18)),
                ("currency", models.CharField(max_length=10)),
                ("policy_version", models.PositiveIntegerField(default=1)),
                ("policy_content", models.TextField(blank=True)),
                ("seller_acknowledged_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("product", models.ForeignKey(on_delete=models.deletion.PROTECT, related_name="versions", to="marketplace.product")),
            ],
            options={"ordering": ["-version"]},
        ),
        migrations.AddConstraint(
            model_name="listingversion",
            constraint=models.UniqueConstraint(fields=("product", "version"), name="unique_product_listing_version"),
        ),
        migrations.AddField(model_name="order", name="listing_version", field=models.PositiveIntegerField(default=1)),
        migrations.AddField(model_name="order", name="product_title_snapshot", field=models.CharField(blank=True, max_length=200)),
        migrations.AddField(model_name="order", name="description_snapshot", field=models.TextField(blank=True)),
        migrations.AddField(model_name="order", name="condition_snapshot", field=models.CharField(blank=True, max_length=80)),
        migrations.AddField(model_name="order", name="specifications_snapshot", field=models.JSONField(blank=True, default=dict)),
        migrations.AddField(model_name="order", name="seller_terms_snapshot", field=models.TextField(blank=True)),
        migrations.AddField(model_name="order", name="policy_version_snapshot", field=models.PositiveIntegerField(default=1)),
        migrations.AddField(model_name="order", name="policy_content_snapshot", field=models.TextField(blank=True)),
        migrations.AddField(model_name="order", name="buyer_disclosure_acknowledged_at", field=models.DateTimeField(blank=True, null=True)),
        migrations.RunPython(seed_policy, migrations.RunPython.noop),
    ]
