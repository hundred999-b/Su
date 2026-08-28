from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):
    initial=True
    dependencies=[
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("marketplace","0001_initial"),
        ("telegram_integration","0002_notifications"),
    ]
    operations=[
        migrations.CreateModel(name="TermsDocument",fields=[
            ("id",models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name="ID")),
            ("kind",models.CharField(choices=[("seller","Seller"),("buyer","Buyer"),("marketplace","Marketplace"),("escrow","Escrow")],max_length=20)),
            ("version",models.CharField(max_length=40)),("title",models.CharField(max_length=200)),("body",models.TextField()),("active",models.BooleanField(default=False)),("created_at",models.DateTimeField(auto_now_add=True)),
            ("created_by",models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,related_name="stage4_terms_created",to=settings.AUTH_USER_MODEL))]),
        migrations.CreateModel(name="ListingRule",fields=[
            ("id",models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name="ID")),("singleton",models.BooleanField(default=True,editable=False,unique=True)),("min_description_chars",models.PositiveIntegerField(default=80)),("max_description_chars",models.PositiveIntegerField(default=10000)),("require_accuracy_confirmation",models.BooleanField(default=True)),("require_seller_terms",models.BooleanField(default=True)),("lock_title_after_order",models.BooleanField(default=True)),("lock_description_after_order",models.BooleanField(default=True)),("lock_price_after_order",models.BooleanField(default=True)),("prohibited_keywords",models.JSONField(blank=True,default=list)),("updated_at",models.DateTimeField(auto_now=True))]),
        migrations.CreateModel(name="TermsAcceptance",fields=[
            ("id",models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name="ID")),("purpose",models.CharField(default="general",max_length=40)),("accepted_at",models.DateTimeField(auto_now_add=True)),("ip_address",models.GenericIPAddressField(blank=True,null=True)),("user_agent",models.TextField(blank=True)),
            ("terms",models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,related_name="acceptances",to="stage4.termsdocument")),("user",models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,related_name="stage4_terms_acceptances",to=settings.AUTH_USER_MODEL))]),
        migrations.AddConstraint(model_name="termsdocument",constraint=models.UniqueConstraint(fields=("kind","version"),name="stage4_terms_kind_version")),
        migrations.CreateModel(name="ListingVersion",fields=[
            ("id",models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name="ID")),("version",models.PositiveIntegerField()),("title",models.CharField(max_length=200)),("description",models.TextField()),("category",models.CharField(blank=True,max_length=80)),("price",models.DecimalField(decimal_places=2,max_digits=18)),("currency",models.CharField(max_length=10)),("accuracy_confirmed",models.BooleanField(default=False)),("fee_disclosed",models.BooleanField(default=False)),("published_at",models.DateTimeField(auto_now_add=True)),("metadata",models.JSONField(blank=True,default=dict)),("seller_terms",models.ForeignKey(blank=True,null=True,on_delete=django.db.models.deletion.PROTECT,to="stage4.termsdocument")),("product",models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,related_name="stage4_versions",to="marketplace.product"))]),
        migrations.AddConstraint(model_name="listingversion",constraint=models.UniqueConstraint(fields=("product","version"),name="stage4_listing_product_version")),
        migrations.CreateModel(name="OrderListingSnapshot",fields=[
            ("id",models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name="ID")),("title",models.CharField(max_length=200)),("description",models.TextField()),("category",models.CharField(blank=True,max_length=80)),("price",models.DecimalField(decimal_places=2,max_digits=18)),("currency",models.CharField(max_length=10)),("captured_at",models.DateTimeField(auto_now_add=True)),
            ("listing_version",models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,to="stage4.listingversion")),("order",models.OneToOneField(on_delete=django.db.models.deletion.PROTECT,related_name="stage4_listing_snapshot",to="marketplace.order")),("product",models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,to="marketplace.product"))]),
        migrations.CreateModel(name="DisputeEvent",fields=[
            ("id",models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name="ID")),("event_type",models.CharField(max_length=50)),("message",models.TextField()),("created_at",models.DateTimeField(auto_now_add=True)),("metadata",models.JSONField(blank=True,default=dict)),
            ("actor",models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,to=settings.AUTH_USER_MODEL)),("order",models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,related_name="stage4_dispute_events",to="marketplace.order"))]),
        migrations.CreateModel(name="VendorVerification",fields=[
            ("id",models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name="ID")),("status",models.CharField(choices=[("pending","Pending"),("approved","Approved"),("rejected","Rejected")],default="pending",max_length=20)),("notes",models.TextField(blank=True)),("reviewed_at",models.DateTimeField(blank=True,null=True)),
            ("reviewed_by",models.ForeignKey(blank=True,null=True,on_delete=django.db.models.deletion.PROTECT,related_name="stage4_vendor_reviews",to=settings.AUTH_USER_MODEL)),("user",models.OneToOneField(on_delete=django.db.models.deletion.PROTECT,related_name="stage4_vendor_verification",to=settings.AUTH_USER_MODEL))]),
        migrations.CreateModel(name="AdminAnnouncement",fields=[
            ("id",models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name="ID")),("title",models.CharField(max_length=160)),("message",models.TextField()),("active",models.BooleanField(default=True)),("created_at",models.DateTimeField(auto_now_add=True)),("created_by",models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,to=settings.AUTH_USER_MODEL))]),
        migrations.CreateModel(name="NotificationDelivery",fields=[
            ("id",models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name="ID")),("channel",models.CharField(default="telegram",max_length=30)),("status",models.CharField(default="pending",max_length=20)),("attempts",models.PositiveIntegerField(default=0)),("telegram_message_id",models.CharField(blank=True,max_length=80)),("last_error",models.TextField(blank=True)),("sent_at",models.DateTimeField(blank=True,null=True)),("updated_at",models.DateTimeField(auto_now=True)),
            ("notification",models.OneToOneField(on_delete=django.db.models.deletion.CASCADE,related_name="stage4_delivery",to="telegram_integration.notification"))]),
    ]
