from django import forms
from django.contrib.auth.forms import UserChangeForm
from django.contrib.auth import get_user_model
from django.apps import apps
from .models import StaffRole


def permission_choices():
    choices = []
    for model in apps.get_models():
        if model._meta.abstract or model._meta.auto_created:
            continue
        app = model._meta.app_label
        name = model._meta.model_name
        label = f"{app}.{name}"
        for action in ("view", "add", "change", "delete", "approve", "reject", "review", "verify", "settle", "release", "refund", "manage"):
            choices.append((f"{app}.{name}.{action}", f"{label} — {action}"))
    choices.sort(key=lambda item: item[1].lower())
    return choices

class StaffRoleForm(forms.ModelForm):
    permissions = forms.MultipleChoiceField(
        choices=(), required=False, widget=forms.CheckboxSelectMultiple,
        help_text="Select exactly what this staff role can view/create/edit/delete. Super Admin bypasses all role limits.",
    )
    class Meta:
        model = StaffRole
        fields = ("name", "description", "active", "permissions", "max_approval_amount", "users")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["permissions"].choices = permission_choices()
        if self.instance and self.instance.pk:
            self.initial["permissions"] = self.instance.permissions or []

    def clean_permissions(self):
        return list(self.cleaned_data.get("permissions") or [])


class ShopUUserChangeForm(UserChangeForm):
    """Prevent non-superusers from changing account privilege controls."""
    class Meta:
        model = get_user_model()
        fields = "__all__"

    def __init__(self, *args, request=None, **kwargs):
        self.request = request
        super().__init__(*args, **kwargs)

        if request is not None and not request.user.is_superuser:
            for name in ("is_superuser", "is_staff", "groups", "user_permissions"):
                field = self.fields.get(name)
                if field is not None:
                    field.disabled = True
                    field.required = False

    def clean(self):
        cleaned = super().clean()

        if self.request is not None and not self.request.user.is_superuser:
            if self.instance.pk:
                protected = {
                    "is_superuser": self.instance.is_superuser,
                    "is_staff": self.instance.is_staff,
                    "groups": list(self.instance.groups.values_list("pk", flat=True)),
                    "user_permissions": list(self.instance.user_permissions.values_list("pk", flat=True)),
                }

                if cleaned.get("is_superuser") != protected["is_superuser"]:
                    raise forms.ValidationError("You cannot change superuser status.")

                if cleaned.get("is_staff") != protected["is_staff"]:
                    raise forms.ValidationError("You cannot change staff status.")

                if set(cleaned.get("groups").values_list("pk", flat=True)) != set(protected["groups"]):
                    raise forms.ValidationError("You cannot change user groups.")

                if set(cleaned.get("user_permissions").values_list("pk", flat=True)) != set(protected["user_permissions"]):
                    raise forms.ValidationError("You cannot change user permissions.")

        return cleaned
