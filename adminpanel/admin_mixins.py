from django.contrib import admin
from .models import StaffRole


STAFF_MANAGED_MODELS = {
    ("adminpanel", "staffrole"),
    ("adminpanel", "maintenancelease"),
}


def _permission_keys(request, action):
    """
    Collect permissions from every active StaffRole assigned to the user.

    Supports both:
      1. Old format:
         ["withdrawals.withdrawalrequest.view", "..."]
      2. New format:
         {"view": [...], "change": [...]}
    """
    user = getattr(request, "user", None)

    if not user or not user.is_authenticated:
        return set()

    if user.is_superuser:
        return {"*"}

    roles = StaffRole.objects.filter(
        users=user,
        active=True,
    ).only("permissions")

    keys = set()

    for role in roles:
        permissions = role.permissions or {}

        # New format
        if isinstance(permissions, dict):
            values = permissions.get(action, [])

            if isinstance(values, (list, tuple, set)):
                keys.update(str(v) for v in values)

        # Existing/legacy format
        elif isinstance(permissions, (list, tuple, set)):
            for value in permissions:
                value = str(value)

                # Exact permission
                if value.endswith(f".{action}"):
                    keys.add(value)

                # Wildcard permissions
                elif value.endswith(".*"):
                    keys.add(value)

    return keys


def _allowed(request, model, action):
    user = getattr(request, "user", None)

    if not user or not user.is_authenticated:
        return False

    # Superusers have unrestricted Django Admin access.
    if user.is_superuser:
        return True

    app = model._meta.app_label.lower()
    name = model._meta.model_name.lower()

    # Staff must never manage the RBAC configuration itself.
    if (app, name) in STAFF_MANAGED_MODELS:
        return False

    keys = _permission_keys(request, action)

    candidates = {
        f"{app}.{name}.{action}",
        f"{app}.{name}.*",
        f"{app}.*.{action}",
        f"{app}.*.*",
        f"*.{name}.{action}",
        f"*.{name}.*",
        action,
        "*",
    }

    return bool(keys.intersection(candidates))


class ShopUModelAdmin(admin.ModelAdmin):
    """
    ShopU staff RBAC.

    Superusers bypass this system completely.
    Staff are restricted according to all active roles assigned to them.
    """

    def has_module_permission(self, request):
        return any(
            _allowed(request, self.model, action)
            for action in ("view", "add", "change")
        )

    def has_view_permission(self, request, obj=None):
        return (
            _allowed(request, self.model, "view")
            or _allowed(request, self.model, "change")
        )

    def has_add_permission(self, request):
        return _allowed(request, self.model, "add")

    def has_change_permission(self, request, obj=None):
        return _allowed(request, self.model, "change")

    def has_delete_permission(self, request, obj=None):
        return _allowed(request, self.model, "delete")
