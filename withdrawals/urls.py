from django.urls import path

from .views import (
    create_paystack_recipient,
    create_paystack_withdrawal,
    paystack_transfer_webhook,
    stripe_connect_webhook,
    airwallex_webhook,
    mangopay_webhook,
    nowpayments_webhook,
)

urlpatterns = [
    path(
        "paystack/recipient/",
        create_paystack_recipient,
        name="paystack-recipient",
    ),
    path(
        "paystack/create/",
        create_paystack_withdrawal,
        name="paystack-withdrawal",
    ),
    path(
        "paystack/webhook/",
        paystack_transfer_webhook,
        name="paystack-transfer-webhook",
    ),
    path(
        "stripe_connect/webhook/",
        stripe_connect_webhook,
        name="stripe-connect-webhook",
    ),
    path(
        "airwallex/webhook/",
        airwallex_webhook,
        name="airwallex-webhook",
    ),
    path(
        "mangopay/webhook/",
        mangopay_webhook,
        name="mangopay-webhook",
    ),
    path(
        "nowpayments/webhook/",
        nowpayments_webhook,
        name="nowpayments-webhook",
    ),
]
