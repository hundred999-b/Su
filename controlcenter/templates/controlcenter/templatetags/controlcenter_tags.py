import json

from django import template

register = template.Library()


@register.filter
def field_value(obj, field_name):
    try:
        value = getattr(obj, field_name)
    except (AttributeError, TypeError):
        return ""

    if callable(value):
        try:
            value = value()
        except TypeError:
            return ""

    if value is None:
        return "—"

    if isinstance(value, (dict, list, tuple)):
        try:
            return json.dumps(
                value,
                indent=2,
                ensure_ascii=False,
                default=str,
            )
        except Exception:
            return str(value)

    return value


@register.filter
def get_item(value, key):
    if isinstance(value, dict):
        return value.get(key, "")
    return ""


@register.filter
def status_class(value):
    value = str(value or "").lower()

    if value in {
        "completed",
        "succeeded",
        "verified",
        "trusted",
        "released",
        "delivered",
        "active",
    }:
        return "success"

    if value in {
        "pending",
        "processing",
        "waiting_agent",
        "assigned",
        "holding",
        "funded",
        "created",
        "open",
    }:
        return "warning"

    if value in {
        "failed",
        "cancelled",
        "refunded",
        "revoked",
        "suspended",
        "closed",
        "expired",
        "disputed",
        "disabled",
    }:
        return "danger"

    return "neutral"
