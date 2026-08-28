from django.contrib.auth.models import User
from django.db import models

class Profile(models.Model):
    BUYER = 'buyer'; SELLER = 'seller'
    ROLE_CHOICES = [(BUYER,'Buyer'),(SELLER,'Seller')]
    user = models.OneToOneField(User,on_delete=models.CASCADE,related_name='profile')
    role = models.CharField(max_length=20,choices=ROLE_CHOICES,default=BUYER)
    profile_image = models.ImageField(upload_to='profiles/', blank=True, null=True)
    phone = models.CharField(max_length=40,blank=True)
    country = models.CharField(max_length=100,blank=True)
    verified = models.BooleanField(default=False)
    telegram_id = models.CharField(max_length=64,blank=True,db_index=True)
    last_seen_at = models.DateTimeField(null=True,blank=True)
    presence_enabled = models.BooleanField(default=True)
    suspended = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    def __str__(self): return f'{self.user.username} - {self.role}'
