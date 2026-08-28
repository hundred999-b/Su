from django.contrib import admin
from .models import StaffRole


def _keys(request, action):
    if request.user.is_superuser:
        return {"*"}
    roles = StaffRole.objects.filter(users=request.user, active=True).only("permissions")
    keys = set()
    for role in roles:
        for raw in role.permissions or []:
            keys.add(str(raw).strip().lower())
    return keys


def _allowed(request, model, action):
    if request.user.is_superuser:
        return True
    if model._meta.app_label == "adminpanel" and model._meta.model_name in {"staffrole", "maintenancelease"}:
        return False
    keys = _keys(request, action)
    app = model._meta.app_label.lower()
    name = model._meta.model_name.lower()
    candidates = {
        f"{app}.{name}.{action}",
        f"{app}.{name}.*",
        f"{app}.*.{action}",
        f"{app}.*.*",
        f"*.{name}.{action}",
        f"*.{name}.*",
        f"{action}",
    }
    return bool(keys.intersection(candidates))


class ShopUModelAdmin(admin.ModelAdmin):
    """Per-model staff RBAC. Superusers bypass it; staff only see granted areas."""
    def has_module_permission(self, request):
        return _allowed(request, self.model, "view") or _allowed(request, self.model, "change") or _allowed(request, self.model, "add")

    def has_view_permission(self, request, obj=None):
        return _allowed(request, self.model, "view") or _allowed(request, self.model, "change")

    def has_add_permission(self, request):
        return _allowed(request, self.model, "add")

    def has_change_permission(self, request, obj=None):
        return _allowed(request, self.model, "change")

    def has_delete_permission(self, request, obj=None):
        return _allowed(request, self.model, "delete")
