from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render

from adminpanel.models import StaffRole
from adminpanel.forms import StaffRoleForm

from .forms import (
    ControlCenterStaffCreateForm,
    ControlCenterStaffEditForm,
)

User = get_user_model()


def superuser_required(view):
    def wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path())

        if not request.user.is_superuser:
            raise PermissionDenied

        return view(request, *args, **kwargs)

    return wrapped


@login_required
def control_center(request):
    if not request.user.is_superuser:
        return staff_center(request)

    context = {
        "user_count": User.objects.filter(is_active=True).count(),
        "staff_count": User.objects.filter(
            is_active=True,
            is_staff=True,
            is_superuser=False,
        ).count(),
        "role_count": StaffRole.objects.filter(active=True).count(),
        "roles": StaffRole.objects.prefetch_related("users").order_by("name"),
        "django_admin_url": "/admin/",
    }

    return render(
        request,
        "controlcenter/control_center.html",
        context,
    )


@login_required
def staff_center(request):
    user = request.user

    if not user.is_staff:
        raise PermissionDenied

    roles = StaffRole.objects.filter(
        users=user,
        active=True,
    ).only(
        "name",
        "description",
        "permissions",
        "max_approval_amount",
    )

    permissions = set()

    for role in roles:
        data = role.permissions or {}

        if isinstance(data, dict):
            for action, values in data.items():
                if isinstance(values, (list, tuple, set)):
                    permissions.update(
                        str(value)
                        for value in values
                    )

        elif isinstance(data, (list, tuple, set)):
            permissions.update(
                str(value)
                for value in data
            )

    return render(
        request,
        "controlcenter/staff_center.html",
        {
            "roles": roles,
            "permissions": sorted(permissions),
            "django_admin_url": "/admin/",
        },
    )


@superuser_required
def staff_list(request):
    staff = (
        User.objects
        .filter(
            is_staff=True,
            is_superuser=False,
        )
        .prefetch_related("shopu_staff_roles")
        .order_by("-is_active", "username")
    )

    return render(
        request,
        "controlcenter/staff_list.html",
        {"staff": staff},
    )


@superuser_required
def staff_create(request):
    if request.method == "POST":
        form = ControlCenterStaffCreateForm(request.POST)

        if form.is_valid():
            form.save()
            return redirect("controlcenter:staff_list")
    else:
        form = ControlCenterStaffCreateForm()

    return render(
        request,
        "controlcenter/staff_form.html",
        {
            "form": form,
            "title": "Create Staff Account",
            "submit_text": "Create Staff",
        },
    )


@superuser_required
def staff_edit(request, user_id):
    user = get_object_or_404(
        User,
        pk=user_id,
        is_superuser=False,
        is_staff=True,
    )

    if request.method == "POST":
        form = ControlCenterStaffEditForm(
            request.POST,
            instance=user,
        )

        if form.is_valid():
            form.save()
            return redirect("controlcenter:staff_list")
    else:
        form = ControlCenterStaffEditForm(instance=user)

    return render(
        request,
        "controlcenter/staff_form.html",
        {
            "form": form,
            "staff_member": user,
            "title": "Edit Staff Account",
            "submit_text": "Save Staff",
        },
    )


@superuser_required
def toggle_staff(request, user_id):
    if request.method != "POST":
        raise PermissionDenied

    user = get_object_or_404(
        User,
        pk=user_id,
        is_superuser=False,
        is_staff=True,
    )

    user.is_active = not user.is_active
    user.save(update_fields=["is_active"])

    return redirect("controlcenter:staff_list")


@superuser_required
def role_list(request):
    roles = StaffRole.objects.prefetch_related(
        "users"
    ).order_by("name")

    return render(
        request,
        "controlcenter/role_list.html",
        {"roles": roles},
    )


@superuser_required
def role_create(request):
    if request.method == "POST":
        form = StaffRoleForm(request.POST)

        if form.is_valid():
            form.save()
            return redirect("controlcenter:role_list")
    else:
        form = StaffRoleForm()

    return render(
        request,
        "controlcenter/role_form.html",
        {
            "form": form,
            "title": "Create Staff Role",
        },
    )


@superuser_required
def role_edit(request, role_id):
    role = get_object_or_404(StaffRole, pk=role_id)

    if request.method == "POST":
        form = StaffRoleForm(
            request.POST,
            instance=role,
        )

        if form.is_valid():
            form.save()
            return redirect("controlcenter:role_list")
    else:
        form = StaffRoleForm(instance=role)

    return render(
        request,
        "controlcenter/role_form.html",
        {
            "form": form,
            "role": role,
            "title": "Edit Staff Role",
        },
    )


@superuser_required
def role_toggle(request, role_id):
    if request.method != "POST":
        raise PermissionDenied

    role = get_object_or_404(
        StaffRole,
        pk=role_id,
    )

    role.active = not role.active
    role.save(update_fields=["active"])

    return redirect("controlcenter:role_list")
