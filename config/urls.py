"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
from django.conf.urls.static import static
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.conf import settings
from django.urls import include, path
from django.conf.urls.static import static
from marketplace.api import wallet, test_deposit_api
from config.maintenance import auto_release
from config.views import health, home
from telegram_integration.webhook_views import telegram_webhook

urlpatterns = [
    path("telegram/webhook/", telegram_webhook, name="telegram_webhook"),
    path("control-center/", include("controlcenter.urls")),
    path("", home, name="home"),
    path("health/", health, name="health"),
    path("api/support/", include("support.urls")),
    path("api/vendor/", include("vendor_verification.urls")),
    path("api/payments/", include("payments.urls")),
    path("api/withdrawals/", include("withdrawals.urls")),
    path("api/crypto/", include("crypto.urls")),
    path("api/giftcards/", include("giftcards.urls")),
    path("api/maintenance/auto-release/", auto_release),

    path("miniapp/", include("telegram_integration.miniapp_urls")),
    path("api/wallet/", wallet),
    path("api/test-deposit/", test_deposit_api),

    path('admin/', admin.site.urls),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
