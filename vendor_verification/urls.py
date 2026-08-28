from django.urls import path
from . import api

urlpatterns = [
    path("<int:seller_id>/", api.vendor_profile, name="vendor-profile"),
    path("settings/", api.verification_settings, name="verification-settings"),
    path("apply/", api.apply, name="vendor-verification-apply"),
]
