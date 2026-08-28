from django.conf import settings
from django.db import models


class VendorVerification(models.Model):
    PENDING = "pending"
    VERIFIED = "verified"
    TRUSTED = "trusted"
    SUSPENDED = "suspended"
    REVOKED = "revoked"

    STATUSES = [
        (PENDING, "Pending"),
        (VERIFIED, "Verified"),
        (TRUSTED, "Trusted Vendor"),
        (SUSPENDED, "Suspended"),
        (REVOKED, "Revoked"),
    ]

    seller = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="vendor_verification",
    )

    status = models.CharField(
        max_length=20,
        choices=STATUSES,
        default=PENDING,
    )

    identity_verified = models.BooleanField(default=False)
    business_verified = models.BooleanField(default=False)
    payment_history_verified = models.BooleanField(default=False)
    transaction_history_verified = models.BooleanField(default=False)

    notes = models.TextField(blank=True)

    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="vendor_verifications_performed",
    )
    trusted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="vendor_trust_promotions",
    )

    verified_at = models.DateTimeField(null=True, blank=True)
    trusted_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    trusted_reason = models.TextField(blank=True)
    caution_override = models.BooleanField(null=True, blank=True, default=None)
    caution_note = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def is_trusted(self):
        return self.status == self.TRUSTED

    @property
    def badge(self):
        return {
            self.VERIFIED: "Verified Vendor",
            self.TRUSTED: "Trusted Vendor",
            self.SUSPENDED: "Suspended",
            self.REVOKED: "Verification Revoked",
        }.get(self.status, "")

    @property
    def badge_level(self):
        return {
            self.VERIFIED: "verified",
            self.TRUSTED: "trusted",
            self.SUSPENDED: "suspended",
            self.REVOKED: "revoked",
            self.PENDING: "pending",
        }.get(self.status, "pending")

    def __str__(self):
        return f"{self.seller.username} — {self.get_status_display()}"


class VendorComplaint(models.Model):
    OPEN = "open"
    SUBSTANTIATED = "substantiated"
    DISMISSED = "dismissed"
    RESOLVED = "resolved"
    STATUS_CHOICES = [
        (OPEN, "Open"),
        (SUBSTANTIATED, "Substantiated"),
        (DISMISSED, "Dismissed"),
        (RESOLVED, "Resolved"),
    ]
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"
    SEVERITY_CHOICES = [
        (LOW, "Low"), (MEDIUM, "Medium"), (HIGH, "High"), (CRITICAL, "Critical"),
    ]

    seller = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="vendor_complaints")
    reporter = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="vendor_complaints_reported")
    order = models.ForeignKey("marketplace.Order", on_delete=models.PROTECT, null=True, blank=True, related_name="vendor_complaints")
    ticket = models.ForeignKey("support.Ticket", on_delete=models.PROTECT, null=True, blank=True, related_name="vendor_complaints")
    category = models.CharField(max_length=60, default="other")
    severity = models.CharField(max_length=20, choices=SEVERITY_CHOICES, default=MEDIUM)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=OPEN, db_index=True)
    description = models.TextField(max_length=10000)
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="vendor_complaints_reviewed")
    resolution_note = models.TextField(max_length=5000, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=("seller", "status")),
            models.Index(fields=("seller", "severity")),
        ]

    def __str__(self):
        return f"Complaint #{self.pk} against {self.seller.username}"


class VendorTrustSettings(models.Model):
    singleton = models.BooleanField(default=True, unique=True, editable=False)
    caution_dispute_threshold = models.PositiveIntegerField(default=3)
    caution_complaint_threshold = models.PositiveIntegerField(default=2)
    caution_dispute_rate_percent = models.PositiveIntegerField(default=20)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def get_solo(cls):
        return cls.objects.get_or_create(pk=1)[0]

    def __str__(self):
        return "ShopU Vendor Trust Settings"


class VerificationProgramSettings(models.Model):
    """Admin-controlled optional vendor verification process."""
    singleton = models.BooleanField(default=True, unique=True, editable=False)
    enabled = models.BooleanField(default=True)
    require_identity = models.BooleanField(default=True)
    require_business = models.BooleanField(default=False)
    require_payment_history = models.BooleanField(default=False)
    require_transaction_history = models.BooleanField(default=True)
    minimum_completed_transactions = models.PositiveIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)
        # Keep legacy built-in toggles synchronized with their corresponding dynamic steps.
        step_model = globals().get("VerificationStep")
        if step_model is not None:
            mapping = {
                "identity": self.require_identity,
                "business": self.require_business,
                "payment_history": self.require_payment_history,
                "transaction_history": self.require_transaction_history,
            }
            for key, required in mapping.items():
                step_model.objects.filter(key=key).update(required=required)

    @classmethod
    def get_solo(cls):
        return cls.objects.get_or_create(pk=1)[0]

    def requirements(self):
        return {
            "identity": self.require_identity,
            "business": self.require_business,
            "payment_history": self.require_payment_history,
            "transaction_history": self.require_transaction_history,
            "minimum_completed_transactions": self.minimum_completed_transactions,
        }

    def __str__(self):
        return "ShopU Vendor Verification Settings"

class VerificationStep(models.Model):
    """Admin-defined verification eligibility/evidence step. Selling never depends on these steps."""
    key = models.SlugField(max_length=80, unique=True)
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    enabled = models.BooleanField(default=True)
    required = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0)
    evidence_type = models.CharField(max_length=30, default="manual", choices=[
        ("manual", "Manual review"),
        ("boolean", "Boolean check"),
        ("document", "Document evidence"),
        ("text", "Text evidence"),
    ])
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["order", "name"]

    def __str__(self):
        return self.name


class VerificationStepResult(models.Model):
    PENDING = "pending"
    PASSED = "passed"
    FAILED = "failed"
    STATUS_CHOICES = [(PENDING, "Pending"), (PASSED, "Passed"), (FAILED, "Failed")]
    verification = models.ForeignKey(VendorVerification, on_delete=models.CASCADE, related_name="step_results")
    step = models.ForeignKey(VerificationStep, on_delete=models.PROTECT, related_name="results")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=PENDING)
    evidence = models.TextField(blank=True)
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="verification_step_reviews")
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewer_note = models.TextField(blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=("verification", "step"), name="unique_vendor_verification_step")]
        ordering = ["step__order", "step__name"]
