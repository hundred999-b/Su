from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
class Review(models.Model):
    buyer=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT,related_name='reviews_written')
    seller=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT,related_name='reviews_received')
    order=models.OneToOneField('marketplace.Order',on_delete=models.PROTECT,related_name='review')
    rating=models.PositiveSmallIntegerField(validators=[MinValueValidator(1),MaxValueValidator(5)])
    comment=models.TextField(max_length=2000,blank=True)
    edited=models.BooleanField(default=False)
    visible=models.BooleanField(default=True)
    moderation_note=models.CharField(max_length=255,blank=True)
    created_at=models.DateTimeField(auto_now_add=True)
    updated_at=models.DateTimeField(auto_now=True)
    class Meta: ordering=['-created_at']
    def __str__(self): return f'{self.rating}★ - Order #{self.order_id}'
