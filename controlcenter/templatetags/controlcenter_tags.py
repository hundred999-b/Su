from django import template

register = template.Library()


@register.filter
def field_value(obj, field_name):
    try:
        value = getattr(obj, field_name)

        if callable(value):
            value = value()

        if value is None:
            return "—"

        if isinstance(value, (dict, list)):
            return str(value)

        return value
    except Exception:
        return "—"


@register.filter
def get_item(dictionary, key):
    if not dictionary:
        return ""

    return dictionary.get(key, "")


@register.filter
def status_class(value):
    """
    Convert a status value into a safe CSS class.
    Example:
        Pending -> pending
        COMPLETED -> completed
        In Progress -> in-progress
    """
    if value is None:
        return ""

    try:
        value = str(value).strip().lower()
    except Exception:
        return ""

    replacements = {
        " ": "-",
        "_": "-",
    }

    for old, new in replacements.items():
        value = value.replace(old, new)

    allowed = "abcdefghijklmnopqrstuvwxyz0123456789-"

    value = "".join(
        char for char in value
        if char in allowed
    )

    return value
