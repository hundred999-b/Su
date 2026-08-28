from django.conf import settings
from django.db import models
from marketplace.models import Order

class Escrow(models.Model):
    HOLDING='holding'; RELEASED='released'; REFUNDED='refunded'; DISPUTED='disputed'
    STATUS_CHOICES=[(HOLDING,'Holding'),(RELEASED,'Released'),(REFUNDED,'Refunded'),(DISPUTED,'Disputed')]
    order=models.OneToOneField(Order,on_delete=models.PROTECT)
    amount=models.DecimalField(max_digits=24,decimal_places=8)
    currency=models.CharField(max_length=10)
    status=models.CharField(max_length=20,choices=STATUS_CHOICES,default=HOLDING)
    created_at=models.DateTimeField(auto_now_add=True)
    released_at=models.DateTimeField(null=True,blank=True)
    funding_transaction_id=models.CharField(max_length=64, blank=True)
    funded_cash_amount=models.DecimalField(max_digits=24, decimal_places=8, default=0)
    funded_gift_amount=models.DecimalField(max_digits=24, decimal_places=8, default=0)

    class Meta:
        permissions = [
            ("settle_escrow", "Can settle escrow"),
        ]

    def __str__(self): return f'Marketplace Escrow #{self.pk}'

class PrivateEscrow(models.Model):
    CREATED='created'; FUNDED='funded'; DELIVERED='delivered'; RELEASED='released'; REFUNDED='refunded'; DISPUTED='disputed'; CANCELLED='cancelled'
    STATUS_CHOICES=[(x,x.title()) for x in [CREATED,FUNDED,DELIVERED,RELEASED,REFUNDED,DISPUTED,CANCELLED]]
    escrow_id=models.CharField(max_length=20,unique=True,db_index=True)
    seller=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT,related_name='private_escrows_as_seller')
    buyer=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT,null=True,blank=True,related_name='private_escrows_as_buyer')
    title=models.CharField(max_length=200)
    description=models.TextField(blank=True)
    amount=models.DecimalField(max_digits=24,decimal_places=8)
    currency=models.CharField(max_length=10,default='USD')
    status=models.CharField(max_length=20,choices=STATUS_CHOICES,default=CREATED)
    created_at=models.DateTimeField(auto_now_add=True)
    funded_at=models.DateTimeField(null=True,blank=True)
    delivered_at=models.DateTimeField(null=True,blank=True)
    deadline=models.DateTimeField(null=True,blank=True)
    released_at=models.DateTimeField(null=True,blank=True)
    funding_transaction_id=models.CharField(max_length=64, blank=True)
    funded_cash_amount=models.DecimalField(max_digits=24, decimal_places=8, default=0)
    funded_gift_amount=models.DecimalField(max_digits=24, decimal_places=8, default=0)
    def __str__(self): return self.escrow_id
