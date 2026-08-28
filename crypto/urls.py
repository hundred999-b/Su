from django.urls import path
from .views import initialize_crypto_payment, nowpayments_ipn

urlpatterns = [
    path("initialize/", initialize_crypto_payment),
    path("nowpayments/ipn/", nowpayments_ipn),
]
