from django.contrib.auth.models import User
from django.db import models


class AuditEvent(models.Model):
    actor = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )

    action = models.CharField(
        max_length=120,
    )

    object_type = models.CharField(
        max_length=120,
        blank=True,
    )

    object_id = models.CharField(
        max_length=120,
        blank=True,
    )

    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
    )

    metadata = models.JSONField(
        default=dict,
        blank=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    def __str__(self):
        return f"{self.action} @ {self.created_at}"
