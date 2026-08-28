from django.conf import settings
from django.db import models

class StaffRole(models.Model):
    name = models.CharField(max_length=80, unique=True)
    description = models.CharField(max_length=255, blank=True)
    active = models.BooleanField(default=True)
    permissions = models.JSONField(default=list, blank=True)
    max_approval_amount = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)
    users = models.ManyToManyField(settings.AUTH_USER_MODEL, related_name='shopu_staff_roles', blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

class StaffAction(models.Model):
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='shopu_staff_actions')
    action = models.CharField(max_length=120)
    object_type = models.CharField(max_length=80, blank=True)
    object_id = models.CharField(max_length=80, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

class MaintenanceLease(models.Model):
    singleton = models.BooleanField(default=True, unique=True, editable=False)
    locked_until = models.DateTimeField(null=True, blank=True)
    last_started_at = models.DateTimeField(null=True, blank=True)
    last_finished_at = models.DateTimeField(null=True, blank=True)
    last_result = models.JSONField(default=dict, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def get_solo(cls):
        return cls.objects.get_or_create(pk=1)[0]


class BackgroundJob(models.Model):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    STATUS_CHOICES = [(PENDING, "Pending"), (RUNNING, "Running"), (COMPLETED, "Completed"), (FAILED, "Failed")]

    kind = models.CharField(max_length=100, db_index=True)
    dedupe_key = models.CharField(max_length=180, unique=True)
    payload = models.JSONField(default=dict, blank=True)
    result = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=PENDING, db_index=True)
    run_after = models.DateTimeField(db_index=True)
    attempts = models.PositiveIntegerField(default=0)
    max_attempts = models.PositiveIntegerField(default=5)
    locked_until = models.DateTimeField(null=True, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=("status", "run_after")),
            models.Index(fields=("kind", "status")),
        ]

    def __str__(self):
        return f"{self.kind} #{self.pk} ({self.status})"
