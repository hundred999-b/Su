from django.urls import path

from . import views

app_name = "controlcenter"

urlpatterns = [

    # ========================================================
    # DASHBOARD
    # ========================================================

    path(
        "",
        views.control_center,
        name="control_center",
    ),

    path(
        "staff/",
        views.staff_center,
        name="staff_center",
    ),

    # ========================================================
    # GENERIC CONTROL CENTER
    # ========================================================

    path(
        "section/<slug:section>/",
        views.section_list,
        name="section_list",
    ),

    path(
        "section/<slug:section>/create/",
        views.section_edit,
        name="section_create",
    ),

    path(
        "section/<slug:section>/<int:object_id>/",
        views.section_detail,
        name="section_detail",
    ),

    path(
        "section/<slug:section>/<int:object_id>/edit/",
        views.section_edit,
        name="section_edit",
    ),

    path(
        "section/<slug:section>/<int:object_id>/action/<slug:action>/",
        views.section_action,
        name="section_action",
    ),

    # ========================================================
    # STAFF
    # ========================================================

    path(
        "manage/staff/",
        views.staff_list,
        name="staff_list",
    ),

    path(
        "manage/staff/create/",
        views.staff_create,
        name="staff_create",
    ),

    path(
        "manage/staff/<int:user_id>/edit/",
        views.staff_edit,
        name="staff_edit",
    ),

    path(
        "manage/staff/<int:user_id>/toggle/",
        views.toggle_staff,
        name="toggle_staff",
    ),

    # ========================================================
    # ROLES
    # ========================================================

    path(
        "manage/roles/",
        views.role_list,
        name="role_list",
    ),

    path(
        "manage/roles/create/",
        views.role_create,
        name="role_create",
    ),

    path(
        "manage/roles/<int:role_id>/edit/",
        views.role_edit,
        name="role_edit",
    ),

    path(
        "manage/roles/<int:role_id>/toggle/",
        views.role_toggle,
        name="role_toggle",
    ),
]
