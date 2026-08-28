from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm, UserChangeForm

from adminpanel.models import StaffRole

User = get_user_model()


class ControlCenterStaffCreateForm(UserCreationForm):
    email = forms.EmailField(required=False)
    first_name = forms.CharField(required=False)
    last_name = forms.CharField(required=False)

    roles = forms.ModelMultipleChoiceField(
        queryset=StaffRole.objects.filter(active=True).order_by("name"),
        required=False,
        widget=forms.CheckboxSelectMultiple,
        help_text="Assign one or more active staff roles.",
    )

    class Meta:
        model = User
        fields = (
            "username",
            "email",
            "first_name",
            "last_name",
            "password1",
            "password2",
            "roles",
        )

    def save(self, commit=True):
        user = super().save(commit=False)

        # Staff created here are ordinary staff accounts.
        user.is_staff = True
        user.is_superuser = False

        if commit:
            user.save()
            self.save_roles(user)

        return user

    def save_roles(self, user):
        user.shopu_staff_roles.set(self.cleaned_data.get("roles", []))


class ControlCenterStaffEditForm(forms.ModelForm):
    email = forms.EmailField(required=False)

    roles = forms.ModelMultipleChoiceField(
        queryset=StaffRole.objects.filter(active=True).order_by("name"),
        required=False,
        widget=forms.CheckboxSelectMultiple,
    )

    class Meta:
        model = User
        fields = (
            "username",
            "email",
            "first_name",
            "last_name",
            "is_active",
            "roles",
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if self.instance and self.instance.pk:
            self.initial["roles"] = self.instance.shopu_staff_roles.filter(
                active=True
            )

    def save(self, commit=True):
        user = super().save(commit=commit)

        if commit:
            user.is_staff = True
            user.is_superuser = False
            user.save(update_fields=["is_staff", "is_superuser"])
            user.shopu_staff_roles.set(
                self.cleaned_data.get("roles", [])
            )

        return user
