from django.urls import path
from . import views

urlpatterns = [
    path("topups/submit/", views.submit_gift_card_topup_api, name="gift-card-topup-submit"),
    path("buy/", views.buy_gift_card, name="gift-card-buy"),
]
