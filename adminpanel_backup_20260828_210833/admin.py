from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from adminpanel.admin_mixins import ShopUModelAdmin, _allowed
from .forms import StaffRoleForm, ShopUUserChangeForm
from .models import StaffRole, StaffAction, MaintenanceLease

User = get_user_model()

@admin.register(StaffRole)
class StaffRoleAdmin(ShopUModelAdmin):
    form = StaffRoleForm
    list_display = ('name', 'active', 'max_approval_amount', 'created_at')
    search_fields = ('name', 'description')
    filter_horizontal = ('users',)

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        # Assigned staff receive their own normal Django login; never share the Super Admin password.
        for user in form.instance.users.all():
            if not user.is_staff:
                user.is_staff = True
                user.save(update_fields=["is_staff"])

@admin.register(StaffAction)
class StaffActionAdmin(ShopUModelAdmin):
    list_display = ('actor', 'action', 'object_type', 'object_id', 'created_at')
    search_fields = ('actor__username', 'action', 'object_id')
    list_filter = ('action', 'object_type')
    readonly_fields = tuple(f.name for f in StaffAction._meta.fields)

@admin.register(MaintenanceLease)
class MaintenanceLeaseAdmin(ShopUModelAdmin):
    list_display = ('locked_until', 'last_started_at', 'last_finished_at', 'updated_at')
    readonly_fields = tuple(f.name for f in MaintenanceLease._meta.fields)

try:
    admin.site.unregister(User)
except admin.sites.NotRegistered:
    pass

@admin.register(User)
class ShopUUserAdmin(BaseUserAdmin):
    form = ShopUUserChangeForm
    def has_module_permission(self, request):
        return request.user.is_superuser or _allowed(request, User, "view") or _allowed(request, User, "change")
    def has_view_permission(self, request, obj=None):
        return request.user.is_superuser or _allowed(request, User, "view") or _allowed(request, User, "change")
    def has_add_permission(self, request):
        return request.user.is_superuser or _allowed(request, User, "add")
    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser or _allowed(request, User, "change")
    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser or _allowed(request, User, "delete")

    def get_form(self, request, obj=None, **kwargs):
        kwargs["form"] = self.form
        form = super().get_form(request, obj, **kwargs)

        class RequestBoundUserForm(form):
            def __init__(self, *args, **inner_kwargs):
                inner_kwargs["request"] = request
                super().__init__(*args, **inner_kwargs)

        return RequestBoundUserForm
    list_display = ('username', 'email', 'is_staff', 'is_superuser', 'is_active', 'last_login')
    list_filter = ('is_staff', 'is_superuser', 'is_active')
    search_fields = ('username', 'email', 'first_name', 'last_name')

from .models import BackgroundJob

@admin.register(BackgroundJob)
class BackgroundJobAdmin(ShopUModelAdmin):
    list_display = ("id", "kind", "status", "run_after", "attempts", "created_at", "completed_at")
    list_filter = ("kind", "status")
    search_fields = ("dedupe_key", "last_error")
    readonly_fields = tuple(f.name for f in BackgroundJob._meta.fields)
