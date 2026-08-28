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
