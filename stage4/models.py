from django.conf import settings
from django.db import models
from django.utils import timezone

class TermsDocument(models.Model):
    SELLER="seller"
    BUYER="buyer"
    MARKETPLACE="marketplace"
    ESCROW="escrow"
    PAYMENTS="payments"
    CRYPTO="crypto"
    GIFT_CARDS="gift_cards"
    BANK_TRANSFER="bank_transfer"
    WITHDRAWALS="withdrawals"
    DISPUTES="disputes"
    VENDOR_VERIFICATION="vendor_verification"
    PROHIBITED_ITEMS="prohibited_items"
    PRIVACY="privacy"
    ACCOUNT_SECURITY="account_security"

    TYPE_CHOICES=[
        (SELLER,"Seller"),
        (BUYER,"Buyer"),
        (MARKETPLACE,"Marketplace"),
        (ESCROW,"Escrow"),
        (PAYMENTS,"Payments"),
        (CRYPTO,"Crypto"),
        (GIFT_CARDS,"Gift Cards"),
        (BANK_TRANSFER,"Bank Transfer"),
        (WITHDRAWALS,"Withdrawals"),
        (DISPUTES,"Disputes"),
        (VENDOR_VERIFICATION,"Vendor Verification"),
        (PROHIBITED_ITEMS,"Prohibited Items"),
        (PRIVACY,"Privacy"),
        (ACCOUNT_SECURITY,"Account Security"),
    ]
    kind=models.CharField(max_length=20,choices=TYPE_CHOICES)
    version=models.CharField(max_length=40)
    title=models.CharField(max_length=200)
    body=models.TextField()
    active=models.BooleanField(default=False)
    created_by=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT,related_name="stage4_terms_created")
    created_at=models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints=[models.UniqueConstraint(fields=["kind","version"],name="stage4_terms_kind_version")]
        ordering=["kind","-created_at"]

class TermsAcceptance(models.Model):
    user=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT,related_name="stage4_terms_acceptances")
    terms=models.ForeignKey(TermsDocument,on_delete=models.PROTECT,related_name="acceptances")
    purpose=models.CharField(max_length=40,default="general")
    accepted_at=models.DateTimeField(auto_now_add=True)
    ip_address=models.GenericIPAddressField(null=True,blank=True)
    user_agent=models.TextField(blank=True)

    class Meta:
        constraints=[models.UniqueConstraint(fields=["user","terms","purpose"],name="stage4_terms_acceptance_unique")]

class ListingRule(models.Model):
    singleton=models.BooleanField(default=True,unique=True,editable=False)
    min_description_chars=models.PositiveIntegerField(default=80)
    max_description_chars=models.PositiveIntegerField(default=10000)
    require_accuracy_confirmation=models.BooleanField(default=True)
    require_seller_terms=models.BooleanField(default=True)
    lock_title_after_order=models.BooleanField(default=True)
    lock_description_after_order=models.BooleanField(default=True)
    lock_price_after_order=models.BooleanField(default=True)
    prohibited_keywords=models.JSONField(default=list,blank=True)
    updated_at=models.DateTimeField(auto_now=True)
    def save(self,*args,**kwargs):
        self.pk=1
        super().save(*args,**kwargs)
    @classmethod
    def get_solo(cls):
        return cls.objects.get_or_create(pk=1)[0]

class ListingVersion(models.Model):
    product=models.ForeignKey("marketplace.Product",on_delete=models.PROTECT,related_name="stage4_versions")
    version=models.PositiveIntegerField()
    title=models.CharField(max_length=200)
    description=models.TextField()
    category=models.CharField(max_length=80,blank=True)
    price=models.DecimalField(max_digits=24,decimal_places=8)
    currency=models.CharField(max_length=10)
    seller_terms=models.ForeignKey(TermsDocument,on_delete=models.PROTECT,null=True,blank=True)
    accuracy_confirmed=models.BooleanField(default=False)
    fee_disclosed=models.BooleanField(default=False)
    published_at=models.DateTimeField(auto_now_add=True)
    metadata=models.JSONField(default=dict,blank=True)
    class Meta:
        constraints=[models.UniqueConstraint(fields=["product","version"],name="stage4_listing_product_version")]

class OrderListingSnapshot(models.Model):
    order=models.OneToOneField("marketplace.Order",on_delete=models.PROTECT,related_name="stage4_listing_snapshot")
    product=models.ForeignKey("marketplace.Product",on_delete=models.PROTECT)
    listing_version=models.ForeignKey(ListingVersion,on_delete=models.PROTECT)
    title=models.CharField(max_length=200)
    description=models.TextField()
    category=models.CharField(max_length=80,blank=True)
    price=models.DecimalField(max_digits=24,decimal_places=8)
    currency=models.CharField(max_length=10)
    captured_at=models.DateTimeField(auto_now_add=True)

class NotificationDelivery(models.Model):
    notification=models.OneToOneField("telegram_integration.Notification",on_delete=models.CASCADE,related_name="stage4_delivery")
    channel=models.CharField(max_length=30,default="telegram")
    status=models.CharField(max_length=20,default="pending")
    attempts=models.PositiveIntegerField(default=0)
    telegram_message_id=models.CharField(max_length=80,blank=True)
    last_error=models.TextField(blank=True)
    sent_at=models.DateTimeField(null=True,blank=True)
    updated_at=models.DateTimeField(auto_now=True)

class DisputeEvent(models.Model):
    order=models.ForeignKey("marketplace.Order",on_delete=models.PROTECT,related_name="stage4_dispute_events")
    actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    event_type=models.CharField(max_length=50)
    message=models.TextField()
    created_at=models.DateTimeField(auto_now_add=True)
    metadata=models.JSONField(default=dict,blank=True)


class AdminAnnouncement(models.Model):
    title=models.CharField(max_length=160)
    message=models.TextField()
    active=models.BooleanField(default=True)
    created_by=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    created_at=models.DateTimeField(auto_now_add=True)
