from django.contrib.admin.apps import AdminConfig


class ShopUAdminConfig(AdminConfig):
    """Use ShopU's custom admin site while keeping Django admin compatibility."""
    default_site = "adminpanel.site.ShopUAdminSite"
