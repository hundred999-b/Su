from django.contrib.auth.decorators import login_required
from decimal import Decimal
from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.forms import modelform_factory
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from adminpanel.models import StaffRole, StaffAction
from audit.models import AuditEvent
from marketplace.models import Order, Product
from payments.models import Payment
from escrow.models import Escrow, PrivateEscrow
from withdrawals.models import WithdrawalRequest
from vendor_verification.models import VendorVerification
from support.models import Ticket
from finance.models import (
    FinanceSettings,
    PaymentMethodConfig,
    CryptoAssetConfig,
    CommissionRule,
    SupportedCurrency,
    PaymentGatewayConfig,
    PayoutProviderConfig,
)

from adminpanel.forms import StaffRoleForm
from .forms import (
    ControlCenterStaffCreateForm,
    ControlCenterStaffEditForm,
)

User = get_user_model()


# ============================================================
# SECTION REGISTRY
# ============================================================

SECTION_CONFIG = {
    "users": {
        "title": "Users",
        "icon": "👥",
        "model": User,
        "search": ("username", "email", "first_name", "last_name"),
        "filters": ("is_active", "is_staff"),
        "ordering": "-date_joined",
        "permission": "auth.user",
    },
    "orders": {
        "title": "Orders",
        "icon": "📦",
        "model": Order,
        "search": (
            "idempotency_key",
            "product_title_snapshot",
            "description_snapshot",
            "currency",
        ),
        "filters": ("status", "currency"),
        "ordering": "-created_at",
        "permission": "marketplace.order",
    },
    "products": {
        "title": "Products",
        "icon": "🛍️",
        "model": Product,
        "search": (
            "title",
            "description",
            "category",
            "currency",
        ),
        "filters": ("active", "condition", "currency"),
        "ordering": "-created_at",
        "permission": "marketplace.product",
    },
    "payments": {
        "title": "Payments",
        "icon": "💳",
        "model": Payment,
        "search": (
            "provider",
            "provider_reference",
            "currency",
            "idempotency_key",
        ),
        "filters": ("status", "currency", "provider"),
        "ordering": "-created_at",
        "permission": "payments.payment",
    },
    "escrow": {
        "title": "Escrow",
        "icon": "🔐",
        "model": Escrow,
        "search": (
            "currency",
            "funding_transaction_id",
        ),
        "filters": ("status", "currency"),
        "ordering": "-created_at",
        "permission": "escrow.escrow",
    },
    "private-escrow": {
        "title": "Private Escrow",
        "icon": "🔒",
        "model": PrivateEscrow,
        "search": (
            "escrow_id",
            "title",
            "description",
            "currency",
        ),
        "filters": ("status", "currency"),
        "ordering": "-created_at",
        "permission": "escrow.privateescrow",
    },
    "withdrawals": {
        "title": "Withdrawals",
        "icon": "💸",
        "model": WithdrawalRequest,
        "search": (
            "currency",
            "method",
            "destination_reference",
            "provider",
            "provider_reference",
        ),
        "filters": ("status", "currency", "provider"),
        "ordering": "-created_at",
        "permission": "withdrawals.withdrawalrequest",
    },
    "vendors": {
        "title": "Vendor Verification",
        "icon": "✅",
        "model": VendorVerification,
        "search": ("notes", "trusted_reason", "caution_note"),
        "filters": ("status",),
        "ordering": "-created_at",
        "permission": "vendor_verification.vendorverification",
    },
    "support": {
        "title": "Support Tickets",
        "icon": "🎧",
        "model": Ticket,
        "search": ("subject",),
        "filters": ("status",),
        "ordering": "-created_at",
        "permission": "support.ticket",
    },
    "audit": {
        "title": "Audit",
        "icon": "🧾",
        "model": AuditEvent,
        "search": (
            "action",
            "object_type",
            "object_id",
        ),
        "filters": ("action", "object_type"),
        "ordering": "-created_at",
        "permission": "audit.auditevent",
        "readonly": True,
    },

    # Finance
    "finance-settings": {
        "title": "Finance Settings",
        "icon": "⚙️",
        "model": FinanceSettings,
        "search": ("default_currency",),
        "filters": (),
        "ordering": "-updated_at",
        "permission": "finance.financesettings",
    },
    "payment-methods": {
        "title": "Payment Methods",
        "icon": "💳",
        "model": PaymentMethodConfig,
        "search": ("key", "name"),
        "filters": ("enabled",),
        "ordering": "display_order",
        "permission": "finance.paymentmethodconfig",
    },
    "crypto-assets": {
        "title": "Crypto Assets",
        "icon": "₿",
        "model": CryptoAssetConfig,
        "search": ("asset", "network"),
        "filters": ("enabled", "network"),
        "ordering": "asset",
        "permission": "finance.cryptoassetconfig",
    },
    "commission-rules": {
        "title": "Commission Rules",
        "icon": "📊",
        "model": CommissionRule,
        "search": ("name", "currency"),
        "filters": ("fee_type", "enabled", "currency"),
        "ordering": "name",
        "permission": "finance.commissionrule",
    },
    "currencies": {
        "title": "Supported Currencies",
        "icon": "💱",
        "model": SupportedCurrency,
        "search": ("code", "name", "symbol"),
        "filters": ("enabled", "is_default"),
        "ordering": "code",
        "permission": "finance.supportedcurrency",
    },
    "payment-gateways": {
        "title": "Payment Gateways",
        "icon": "🌐",
        "model": PaymentGatewayConfig,
        "search": ("provider",),
        "filters": ("enabled",),
        "ordering": "priority",
        "permission": "finance.paymentgatewayconfig",
    },
    "payout-providers": {
        "title": "Payout Providers",
        "icon": "🏦",
        "model": PayoutProviderConfig,
        "search": ("provider", "name"),
        "filters": ("enabled",),
        "ordering": "priority",
        "permission": "finance.payoutproviderconfig",
    },
}


# ============================================================
# PERMISSIONS
# ============================================================

def superuser_required(view):
    def wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path())

        if not request.user.is_superuser:
            raise PermissionDenied

        return view(request, *args, **kwargs)

    return wrapped


def _permission_keys(request, action):
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

        if isinstance(permissions, dict):
            values = permissions.get(action, [])

            if isinstance(values, (list, tuple, set)):
                keys.update(str(v) for v in values)

        elif isinstance(permissions, (list, tuple, set)):
            for value in permissions:
                value = str(value)

                if value.endswith(f".{action}"):
                    keys.add(value)

                elif value.endswith(".*"):
                    keys.add(value)

    return keys


def has_control_permission(request, permission, action="view"):
    user = getattr(request, "user", None)

    if not user or not user.is_authenticated:
        return False

    if user.is_superuser:
        return True

    keys = _permission_keys(request, action)

    candidates = {
        f"{permission}.{action}",
        f"{permission}.*",
        action,
        "*",
    }

    return bool(keys.intersection(candidates))


def require_control_permission(request, config, action="view"):
    if not has_control_permission(
        request,
        config["permission"],
        action,
    ):
        raise PermissionDenied


# ============================================================
# AUDIT
# ============================================================

def record_audit(
    request,
    action,
    obj=None,
    metadata=None,
):
    metadata = metadata or {}

    try:
        AuditEvent.objects.create(
            actor=request.user,
            action=action,
            object_type=(
                f"{obj._meta.app_label}.{obj._meta.model_name}"
                if obj is not None
                else "controlcenter"
            ),
            object_id=str(obj.pk) if obj is not None else "",
            ip_address=(
                request.META.get("HTTP_X_FORWARDED_FOR", "").split(",")[0].strip()
                or request.META.get("REMOTE_ADDR")
                or "0.0.0.0"
            ),
            metadata=metadata,
        )
    except Exception:
        # Audit logging must never break the administrative operation.
        pass

    try:
        StaffAction.objects.create(
            actor=request.user,
            action=action,
            object_type=(
                f"{obj._meta.app_label}.{obj._meta.model_name}"
                if obj is not None
                else "controlcenter"
            ),
            object_id=str(obj.pk) if obj is not None else "",
            metadata=metadata,
        )
    except Exception:
        pass


# ============================================================
# DASHBOARD
# ============================================================

@login_required
def control_center(request):
    if not request.user.is_superuser:
        return staff_center(request)

    counts = {
        "users": User.objects.filter(is_active=True).count(),
        "staff": User.objects.filter(
            is_active=True,
            is_staff=True,
            is_superuser=False,
        ).count(),
        "orders": Order.objects.count(),
        "products": Product.objects.count(),
        "payments": Payment.objects.count(),
        "escrow": Escrow.objects.count(),
        "withdrawals": WithdrawalRequest.objects.count(),
        "vendors": VendorVerification.objects.count(),
        "support": Ticket.objects.count(),
        "audit": AuditEvent.objects.count(),
    }

    finance_count = (
        FinanceSettings.objects.count()
        + PaymentMethodConfig.objects.count()
        + CryptoAssetConfig.objects.count()
        + CommissionRule.objects.count()
        + SupportedCurrency.objects.count()
        + PaymentGatewayConfig.objects.count()
        + PayoutProviderConfig.objects.count()
    )

    roles = StaffRole.objects.prefetch_related("users").order_by("name")

    return render(
        request,
        "controlcenter/control_center.html",
        {
            "counts": counts,
            "finance_count": finance_count,
            "roles": roles,
        },
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

    permission_data = {}

    for role in roles:
        data = role.permissions or {}

        if isinstance(data, dict):
            for action, values in data.items():
                if isinstance(values, (list, tuple, set)):
                    permission_data.setdefault(action, set()).update(
                        str(value) for value in values
                    )

        elif isinstance(data, (list, tuple, set)):
            permission_data.setdefault("view", set()).update(
                str(value) for value in data
            )

    sections = []

    for key, config in SECTION_CONFIG.items():
        if has_control_permission(
            request,
            config["permission"],
            "view",
        ):
            sections.append(
                {
                    "key": key,
                    **config,
                }
            )

    return render(
        request,
        "controlcenter/staff_center.html",
        {
            "roles": roles,
            "permissions": permission_data,
            "sections": sections,
        },
    )


# ============================================================
# GENERIC HELPERS
# ============================================================

def get_config(section):
    config = SECTION_CONFIG.get(section)

    if not config:
        raise PermissionDenied

    return config


def get_model_fields(model):
    fields = []

    for field in model._meta.fields:
        if field.auto_created:
            continue

        fields.append(field)

    return fields


def get_display_fields(model):
    fields = []

    for field in model._meta.fields:
        if field.auto_created:
            continue

        fields.append(field)

    return fields


def apply_search(queryset, config, search):
    if not search:
        return queryset

    query = Q()

    for field_name in config.get("search", ()):
        query |= Q(**{f"{field_name}__icontains": search})

    if query:
        queryset = queryset.filter(query)

    return queryset


def apply_filters(queryset, config, request):
    model = config["model"]

    for field_name in config.get("filters", ()):
        value = request.GET.get(field_name)

        if value in (None, ""):
            continue

        field = model._meta.get_field(field_name)

        if field_name in {"is_active", "is_staff", "active", "enabled", "is_default"}:
            if value.lower() in {"1", "true", "yes", "on"}:
                value = True
            elif value.lower() in {"0", "false", "no", "off"}:
                value = False
            else:
                continue

        queryset = queryset.filter(**{field_name: value})

    return queryset


def field_choices(model, field_name):
    try:
        field = model._meta.get_field(field_name)
    except Exception:
        return []

    choices = list(field.choices or [])

    return choices


def make_filter_data(config, request):
    data = []

    for field_name in config.get("filters", ()):
        choices = field_choices(config["model"], field_name)

        if choices:
            data.append(
                {
                    "name": field_name,
                    "label": field_name.replace("_", " ").title(),
                    "choices": choices,
                    "selected": request.GET.get(field_name, ""),
                }
            )

    return data


def build_query_string(request, exclude=None):
    exclude = set(exclude or [])

    values = []

    for key, value in request.GET.items():
        if key in exclude:
            continue

        if key == "page":
            continue

        if value:
            values.append((key, value))

    return urlencode(values)


# ============================================================
# GENERIC LIST
# ============================================================

@login_required
def section_list(request, section):
    config = get_config(section)

    require_control_permission(
        request,
        config,
        "view",
    )

    model = config["model"]

    queryset = model.objects.all()

    search = request.GET.get("q", "").strip()

    queryset = apply_search(
        queryset,
        config,
        search,
    )

    queryset = apply_filters(
        queryset,
        config,
        request,
    )

    ordering = config.get("ordering")

    if ordering:
        queryset = queryset.order_by(ordering)

    paginator = Paginator(
        queryset,
        25,
    )

    page_number = request.GET.get("page")

    page_obj = paginator.get_page(page_number)

    columns = get_display_fields(model)[:8]

    return render(
        request,
        "controlcenter/list.html",
        {
            "section": section,
            "config": config,
            "page_obj": page_obj,
            "columns": columns,
            "search": search,
            "filters": make_filter_data(config, request),
            "query_string": build_query_string(request),
            "can_add": has_control_permission(
                request,
                config["permission"],
                "add",
            ),
            "can_edit": has_control_permission(
                request,
                config["permission"],
                "change",
            ),
        },
    )


# ============================================================
# GENERIC DETAIL
# ============================================================

@login_required
def section_detail(request, section, object_id):
    config = get_config(section)

    require_control_permission(
        request,
        config,
        "view",
    )

    obj = get_object_or_404(
        config["model"],
        pk=object_id,
    )

    fields = get_display_fields(
        config["model"]
    )

    actions = get_available_actions(
        request,
        section,
        obj,
    )

    related = []

    for field in config["model"]._meta.fields:
        if not field.is_relation:
            continue

        try:
            value = getattr(obj, field.name)
        except Exception:
            value = None

        if value is not None:
            related.append(
                {
                    "name": field.name.replace("_", " "),
                    "value": str(value),
                }
            )

    return render(
        request,
        "controlcenter/detail.html",
        {
            "section": section,
            "config": config,
            "object": obj,
            "fields": fields,
            "actions": actions,
            "related": related,
            "can_edit": (
                not config.get("readonly", False)
                and has_control_permission(
                    request,
                    config["permission"],
                    "change",
                )
            ),
        },
    )


# ============================================================
# GENERIC EDIT
# ============================================================

@login_required
def section_edit(request, section, object_id=None):
    config = get_config(section)

    if config.get("readonly"):
        raise PermissionDenied

    action = "add" if object_id is None else "change"

    require_control_permission(
        request,
        config,
        action,
    )

    model = config["model"]

    instance = None

    if object_id is not None:
        instance = get_object_or_404(
            model,
            pk=object_id,
        )

    excluded = {
        "id",
        "password",
        "last_login",
        "date_joined",
    }

    field_names = [
        field.name
        for field in model._meta.fields
        if field.name not in excluded
        and not field.auto_created
        and getattr(field, "editable", True)
    ]

    FormClass = modelform_factory(
        model,
        fields=field_names,
    )

    if request.method == "POST":
        form = FormClass(
            request.POST,
            request.FILES,
            instance=instance,
        )

        if form.is_valid():
            saved = form.save()

            record_audit(
                request,
                "controlcenter.edit",
                saved,
                {
                    "section": section,
                    "created": object_id is None,
                },
            )

            messages.success(
                request,
                f"{config['title']} saved successfully.",
            )

            return redirect(
                "controlcenter:section_detail",
                section=section,
                object_id=saved.pk,
            )

    else:
        form = FormClass(
            instance=instance,
        )

    return render(
        request,
        "controlcenter/form.html",
        {
            "section": section,
            "config": config,
            "form": form,
            "object": instance,
            "title": (
                f"Create {config['title']}"
                if instance is None
                else f"Edit {config['title']} #{instance.pk}"
            ),
        },
    )


# ============================================================
# ACTIONS
# ============================================================

def get_available_actions(request, section, obj):
    actions = []

    config = get_config(section)

    if config.get("readonly"):
        return actions

    if section == "orders":
        if obj.status == "pending":
            actions.append(
                {
                    "key": "mark_paid",
                    "label": "Mark Paid",
                    "danger": False,
                }
            )

        if obj.status in {"paid", "escrow"}:
            actions.append(
                {
                    "key": "mark_delivered",
                    "label": "Mark Delivered",
                    "danger": False,
                }
            )

        if obj.status not in {"completed", "refunded"}:
            actions.append(
                {
                    "key": "refund",
                    "label": "Refund",
                    "danger": True,
                }
            )

    elif section == "products":
        if obj.active:
            actions.append(
                {
                    "key": "deactivate",
                    "label": "Deactivate",
                    "danger": True,
                }
            )
        else:
            actions.append(
                {
                    "key": "activate",
                    "label": "Activate",
                    "danger": False,
                }
            )

    elif section == "withdrawals":
        if obj.status == "pending":
            actions.append(
                {
                    "key": "processing",
                    "label": "Mark Processing",
                    "danger": False,
                }
            )

        if obj.status == "processing":
            actions.append(
                {
                    "key": "complete",
                    "label": "Mark Completed",
                    "danger": False,
                }
            )

        if obj.status not in {"completed", "cancelled"}:
            actions.append(
                {
                    "key": "cancel",
                    "label": "Cancel",
                    "danger": True,
                }
            )

    elif section == "vendors":
        if obj.status in {"pending", "suspended"}:
            actions.append(
                {
                    "key": "verify",
                    "label": "Verify Vendor",
                    "danger": False,
                }
            )

        if obj.status == "verified":
            actions.append(
                {
                    "key": "trust",
                    "label": "Mark Trusted",
                    "danger": False,
                }
            )

        if obj.status in {"verified", "trusted"}:
            actions.append(
                {
                    "key": "suspend",
                    "label": "Suspend",
                    "danger": True,
                }
            )

        if obj.status != "revoked":
            actions.append(
                {
                    "key": "revoke",
                    "label": "Revoke",
                    "danger": True,
                }
            )

    elif section == "support":
        if obj.status == "open":
            actions.append(
                {
                    "key": "assign",
                    "label": "Assign",
                    "danger": False,
                }
            )

        if obj.status in {"open", "waiting_agent", "assigned"}:
            actions.append(
                {
                    "key": "resolve",
                    "label": "Resolve",
                    "danger": False,
                }
            )

        if obj.status != "closed":
            actions.append(
                {
                    "key": "close",
                    "label": "Close",
                    "danger": True,
                }
            )

    elif section in {
        "payment-methods",
        "crypto-assets",
        "currencies",
        "payment-gateways",
        "payout-providers",
        "commission-rules",
    }:
        if hasattr(obj, "enabled"):
            actions.append(
                {
                    "key": "toggle_enabled",
                    "label": (
                        "Disable"
                        if obj.enabled
                        else "Enable"
                    ),
                    "danger": bool(obj.enabled),
                }
            )

    return [
        action
        for action in actions
        if has_control_permission(
            request,
            config["permission"],
            "change",
        )
    ]


@login_required
@require_POST
def section_action(request, section, object_id, action):
    config = get_config(section)

    if config.get("readonly"):
        raise PermissionDenied

    require_control_permission(
        request,
        config,
        "change",
    )

    obj = get_object_or_404(
        config["model"],
        pk=object_id,
    )

    valid_actions = {
        item["key"]
        for item in get_available_actions(
            request,
            section,
            obj,
        )
    }

    if action not in valid_actions:
        raise PermissionDenied

    with transaction.atomic():

        # ---------------- ORDER ----------------

        if section == "orders":

            if action == "mark_paid":
                obj.status = "paid"
                obj.save(update_fields=["status"])

            elif action == "mark_delivered":
                obj.status = "delivered"
                obj.save(update_fields=["status"])

            elif action == "refund":
                obj.status = "refunded"
                obj.save(update_fields=["status"])

        # ---------------- PRODUCT ----------------

        elif section == "products":

            if action == "activate":
                obj.active = True
                obj.save(update_fields=["active"])

            elif action == "deactivate":
                obj.active = False
                obj.save(update_fields=["active"])

        # ---------------- WITHDRAWAL ----------------

        elif section == "withdrawals":

            if action == "processing":
                obj.status = "processing"
                obj.save(update_fields=["status"])

            elif action == "complete":
                obj.status = "completed"
                obj.save(update_fields=["status"])

            elif action == "cancel":
                obj.status = "cancelled"
                obj.save(update_fields=["status"])

        # ---------------- VENDOR ----------------

        elif section == "vendors":

            if action == "verify":
                obj.status = "verified"
                obj.identity_verified = True
                obj.verified_by = request.user
                obj.save(
                    update_fields=[
                        "status",
                        "identity_verified",
                        "verified_by",
                    ]
                )

            elif action == "trust":
                obj.status = "trusted"
                obj.trusted_by = request.user
                obj.save(
                    update_fields=[
                        "status",
                        "trusted_by",
                    ]
                )

            elif action == "suspend":
                obj.status = "suspended"
                obj.save(update_fields=["status"])

            elif action == "revoke":
                obj.status = "revoked"
                obj.status = "revoked"
                obj.save(update_fields=["status"])

        # ---------------- SUPPORT ----------------

        elif section == "support":

            if action == "resolve":
                obj.status = "resolved"
                obj.resolved_at = obj.resolved_at or None

                update_fields = ["status"]

                if hasattr(obj, "resolved_at"):
                    from django.utils import timezone

                    obj.resolved_at = timezone.now()
                    update_fields.append("resolved_at")

                obj.save(update_fields=update_fields)

            elif action == "close":
                obj.status = "closed"

                update_fields = ["status"]

                if hasattr(obj, "closed_at"):
                    from django.utils import timezone

                    obj.closed_at = timezone.now()
                    update_fields.append("closed_at")

                obj.save(update_fields=update_fields)

            elif action == "assign":
                obj.status = "assigned"
                obj.assigned_agent = None

                obj.save(
                    update_fields=[
                        "status",
                        "assigned_agent",
                    ]
                )

        # ---------------- CONFIG ----------------

        elif section in {
            "payment-methods",
            "crypto-assets",
            "currencies",
            "payment-gateways",
            "payout-providers",
            "commission-rules",
        }:

            if action == "toggle_enabled":
                obj.enabled = not obj.enabled
                obj.save(update_fields=["enabled"])

    record_audit(
        request,
        f"controlcenter.{section}.{action}",
        obj,
        {
            "section": section,
            "action": action,
        },
    )

    messages.success(
        request,
        f"{config['title']} action '{action}' completed.",
    )

    return redirect(
        "controlcenter:section_detail",
        section=section,
        object_id=obj.pk,
    )


# ============================================================
# STAFF MANAGEMENT
# ============================================================

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

    search = request.GET.get("q", "").strip()

    if search:
        staff = staff.filter(
            Q(username__icontains=search)
            | Q(email__icontains=search)
            | Q(first_name__icontains=search)
            | Q(last_name__icontains=search)
        )

    paginator = Paginator(staff, 25)

    page_obj = paginator.get_page(
        request.GET.get("page")
    )

    return render(
        request,
        "controlcenter/staff_list.html",
        {
            "staff": page_obj,
            "search": search,
        },
    )


@superuser_required
def staff_create(request):
    if request.method == "POST":
        form = ControlCenterStaffCreateForm(
            request.POST
        )

        if form.is_valid():
            user = form.save()

            record_audit(
                request,
                "controlcenter.staff.create",
                user,
            )

            messages.success(
                request,
                "Staff account created.",
            )

            return redirect(
                "controlcenter:staff_list"
            )
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

            record_audit(
                request,
                "controlcenter.staff.edit",
                user,
            )

            messages.success(
                request,
                "Staff account updated.",
            )

            return redirect(
                "controlcenter:staff_list"
            )
    else:
        form = ControlCenterStaffEditForm(
            instance=user
        )

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
@require_POST
def toggle_staff(request, user_id):
    user = get_object_or_404(
        User,
        pk=user_id,
        is_superuser=False,
        is_staff=True,
    )

    user.is_active = not user.is_active

    user.save(
        update_fields=["is_active"]
    )

    record_audit(
        request,
        "controlcenter.staff.toggle",
        user,
        {
            "active": user.is_active,
        },
    )

    return redirect(
        "controlcenter:staff_list"
    )


# ============================================================
# ROLE MANAGEMENT
# ============================================================

@superuser_required
def role_list(request):
    roles = (
        StaffRole.objects
        .prefetch_related("users")
        .order_by("name")
    )

    search = request.GET.get("q", "").strip()

    if search:
        roles = roles.filter(
            Q(name__icontains=search)
            | Q(description__icontains=search)
        )

    return render(
        request,
        "controlcenter/role_list.html",
        {
            "roles": roles,
            "search": search,
        },
    )


@superuser_required
def role_create(request):
    if request.method == "POST":
        form = StaffRoleForm(
            request.POST
        )

        if form.is_valid():
            role = form.save()

            record_audit(
                request,
                "controlcenter.role.create",
                role,
            )

            return redirect(
                "controlcenter:role_list"
            )
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
    role = get_object_or_404(
        StaffRole,
        pk=role_id,
    )

    if request.method == "POST":
        form = StaffRoleForm(
            request.POST,
            instance=role,
        )

        if form.is_valid():
            form.save()

            record_audit(
                request,
                "controlcenter.role.edit",
                role,
            )

            return redirect(
                "controlcenter:role_list"
            )
    else:
        form = StaffRoleForm(
            instance=role
        )

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
@require_POST
def role_toggle(request, role_id):
    role = get_object_or_404(
        StaffRole,
        pk=role_id,
    )

    role.active = not role.active

    role.save(
        update_fields=["active"]
    )

    record_audit(
        request,
        "controlcenter.role.toggle",
        role,
        {
            "active": role.active,
        },
    )

    return redirect(
        "controlcenter:role_list"
    )
