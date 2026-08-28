from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone
from datetime import timedelta


class ListingPolicy(models.Model):
    """Platform listing terms shown to sellers before publishing."""
    key = models.CharField(max_length=80, unique=True, default="seller_listing_terms")
    version = models.PositiveIntegerField(default=1)
    title = models.CharField(max_length=200, default="Seller Listing Terms")
    content = models.TextField()
    active = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-version"]

    def save(self, *args, **kwargs):
        if self.pk:
            previous = type(self).objects.filter(pk=self.pk).first()
            if previous and previous.content != self.content:
                self.version = previous.version + 1
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.title} v{self.version}"


class Product(models.Model):
    seller = models.ForeignKey(User, on_delete=models.PROTECT, related_name='products')
    title = models.CharField(max_length=200)
    description = models.TextField()
    category = models.CharField(max_length=80, blank=True, db_index=True)
    condition = models.CharField(max_length=80, blank=True)
    specifications = models.JSONField(default=dict, blank=True)
    seller_terms = models.TextField(blank=True)
    price = models.DecimalField(max_digits=24, decimal_places=8)
    currency = models.CharField(max_length=10, default='USD')
    image = models.ImageField(upload_to='products/', blank=True, null=True)
    active = models.BooleanField(default=True)
    disclosure_acknowledged = models.BooleanField(default=False)
    fee_acknowledged = models.BooleanField(default=False)
    listing_policy_version = models.PositiveIntegerField(default=1)
    listing_policy_content = models.TextField(blank=True)
    published_at = models.DateTimeField(null=True, blank=True)
    version = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title


class ListingVersion(models.Model):
    """Immutable evidence of the listing shown/published at a point in time."""
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="versions")
    version = models.PositiveIntegerField()
    title = models.CharField(max_length=200)
    description = models.TextField()
    category = models.CharField(max_length=80, blank=True)
    condition = models.CharField(max_length=80, blank=True)
    specifications = models.JSONField(default=dict, blank=True)
    seller_terms = models.TextField(blank=True)
    price = models.DecimalField(max_digits=24, decimal_places=8)
    currency = models.CharField(max_length=10)
    policy_version = models.PositiveIntegerField(default=1)
    policy_content = models.TextField(blank=True)
    seller_acknowledged_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=("product", "version"), name="unique_product_listing_version")
        ]
        ordering = ["-version"]

    def __str__(self):
        return f"{self.product_id} v{self.version}"


class Order(models.Model):
    PENDING='pending'; PAID='paid'; ESCROW='escrow'; DELIVERED='delivered'; COMPLETED='completed'; REFUNDED='refunded'; DISPUTED='disputed'
    STATUS_CHOICES=[(PENDING,'Pending'),(PAID,'Paid'),(ESCROW,'Escrow'),(DELIVERED,'Delivered'),(COMPLETED,'Completed'),(REFUNDED,'Refunded'),(DISPUTED,'Disputed')]
    buyer=models.ForeignKey(User,on_delete=models.PROTECT,related_name='marketplace_orders')
    idempotency_key=models.CharField(max_length=120,unique=True,null=True,blank=True,db_index=True)
    product=models.ForeignKey(Product,on_delete=models.PROTECT)
    amount=models.DecimalField(max_digits=24,decimal_places=8)
    currency=models.CharField(max_length=10)
    listing_version=models.PositiveIntegerField(default=1)
    product_title_snapshot=models.CharField(max_length=200, blank=True)
    description_snapshot=models.TextField(blank=True)
    condition_snapshot=models.CharField(max_length=80, blank=True)
    specifications_snapshot=models.JSONField(default=dict, blank=True)
    seller_terms_snapshot=models.TextField(blank=True)
    policy_version_snapshot=models.PositiveIntegerField(default=1)
    policy_content_snapshot=models.TextField(blank=True)
    buyer_disclosure_acknowledged_at=models.DateTimeField(null=True, blank=True)
    status=models.CharField(max_length=20,choices=STATUS_CHOICES,default=PENDING)
    created_at=models.DateTimeField(auto_now_add=True)
    paid_at=models.DateTimeField(null=True,blank=True)
    delivered_at=models.DateTimeField(null=True,blank=True)
    confirmation_deadline=models.DateTimeField(null=True,blank=True)
    confirmed_at=models.DateTimeField(null=True,blank=True)

    def set_deadline(self,hours=6):
        self.confirmation_deadline=timezone.now()+timedelta(hours=hours)

    def __str__(self):
        return f'Order #{self.pk}'
