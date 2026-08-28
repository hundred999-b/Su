from django.urls import path
from .views import (
    initialize_paystack,
    verify_payment,
    paystack_webhook,
    initialize_stripe,
    stripe_webhook,
    initialize_generic_payment,
)

urlpatterns = [
    path("initialize/", initialize_generic_payment),
    path("paystack/initialize/", initialize_paystack),
    path("paystack/verify/", verify_payment),
    path("paystack/webhook/", paystack_webhook),
    path("stripe/initialize/", initialize_stripe),
    path("stripe/webhook/", stripe_webhook),
]
