from django.db import transaction
from audit.models import AuditEvent
from django.utils import timezone
from marketplace.models import Order
from .models import VendorVerification, VerificationProgramSettings, VerificationStep, VerificationStepResult


def get_vendor_verification(seller):
    return VendorVerification.objects.filter(seller=seller).first()


def sync_step_results(verification):
    for step in VerificationStep.objects.filter(enabled=True):
        VerificationStepResult.objects.get_or_create(verification=verification, step=step)

@transaction.atomic
def apply_for_verification(seller):
    program = VerificationProgramSettings.get_solo()
    if not program.enabled:
        raise ValueError("Vendor verification is currently unavailable.")
    verification, _ = VendorVerification.objects.get_or_create(seller=seller, defaults={"status": VendorVerification.PENDING})
    if verification.status in (VendorVerification.VERIFIED, VendorVerification.TRUSTED):
        return verification
    if verification.status == VendorVerification.SUSPENDED:
        raise ValueError("This vendor is not currently eligible to apply.")
    verification.status = VendorVerification.PENDING
    verification.save(update_fields=["status", "updated_at"])
    sync_step_results(verification)
    return verification


def verification_requirements_met(seller):
    program = VerificationProgramSettings.get_solo()
    verification = get_vendor_verification(seller)

    if not verification or not program.enabled:
        return False

    completed = Order.objects.filter(
        product__seller=seller,
        status=Order.COMPLETED,
    ).count()

    if completed < program.minimum_completed_transactions:
        return False

    sync_step_results(verification)

    required_steps = VerificationStep.objects.filter(
        enabled=True,
        required=True,
    )

    return all(
        VerificationStepResult.objects.filter(
            verification=verification,
            step=step,
            status=VerificationStepResult.PASSED,
        ).exists()
        for step in required_steps
    )

@transaction.atomic
def set_step_result(*, verification_id, step_id, status, reviewer, evidence="", reviewer_note=""):
    verification = VendorVerification.objects.select_for_update().get(pk=verification_id)
    step = VerificationStep.objects.get(pk=step_id, enabled=True)
    if status not in {VerificationStepResult.PENDING, VerificationStepResult.PASSED, VerificationStepResult.FAILED}:
        raise ValueError("Invalid verification step status.")
    result, _ = VerificationStepResult.objects.select_for_update().get_or_create(verification=verification, step=step)
    result.status = status
    result.evidence = str(evidence or "")[:10000]
    result.reviewer_note = str(reviewer_note or "")[:5000]
    result.reviewed_by = reviewer
    result.reviewed_at = timezone.now()
    result.save()
    return result

@transaction.atomic
def set_vendor_status(seller, status, *, reviewer=None, identity_verified=None, business_verified=None, payment_history_verified=None, transaction_history_verified=None, note=""):
    verification = VendorVerification.objects.filter(seller=seller).first()

    if verification is None:
        if status == VendorVerification.VERIFIED:
            raise ValueError(
                "The vendor must apply for verification before being marked Verified."
            )

        verification = VendorVerification.objects.create(
            seller=seller,
            status=VendorVerification.PENDING,
        )

    if status == VendorVerification.VERIFIED:
        if verification.status not in (
            VendorVerification.PENDING,
            VendorVerification.VERIFIED,
        ):
            raise ValueError(
                "The vendor is not eligible for verification."
            )
    # Legacy booleans are retained for compatibility; dynamic steps are authoritative.
    for field, value in (("identity_verified", identity_verified), ("business_verified", business_verified), ("payment_history_verified", payment_history_verified), ("transaction_history_verified", transaction_history_verified)):
        if value is not None:
            setattr(verification, field, value)
    if note:
        verification.notes = note
    verification.save()
    sync_step_results(verification)
    # Synchronize legacy boolean verification fields with dynamic steps.
    legacy_values = {
        "identity": verification.identity_verified,
        "business": verification.business_verified,
        "payment_history": verification.payment_history_verified,
        "transaction_history": verification.transaction_history_verified,
    }
    explicit_values = {
        "identity": identity_verified,
        "business": business_verified,
        "payment_history": payment_history_verified,
        "transaction_history": transaction_history_verified,
    }

    for key in legacy_values:
        value = explicit_values[key]
        if value is None:
            value = legacy_values[key]

        if value:
            step = VerificationStep.objects.filter(key=key, enabled=True).first()
            if step:
                set_step_result(
                    verification_id=verification.pk,
                    step_id=step.pk,
                    status=VerificationStepResult.PASSED,
                    reviewer=reviewer,
                )
        elif explicit_values[key] is not None:
            step = VerificationStep.objects.filter(key=key, enabled=True).first()
            if step:
                set_step_result(
                    verification_id=verification.pk,
                    step_id=step.pk,
                    status=VerificationStepResult.FAILED,
                    reviewer=reviewer,
                )
    now = timezone.now()
    if status == VendorVerification.VERIFIED:
        if not verification_requirements_met(seller):
            raise ValueError("The vendor has not satisfied the requirements currently configured by admin.")
        verification.verified_at = now
        verification.revoked_at = None
        verification.verified_by = reviewer
    elif status == VendorVerification.TRUSTED:
        # Trusted is an admin reliability designation, not an identity-verification substitute.
        # The admin must decide that the seller is reliable; verification requirements remain
        # authoritative only for the Verified badge.
        verification.trusted_at = now
        verification.trusted_by = reviewer
        verification.revoked_at = None
        if note:
            verification.trusted_reason = note
    elif status == VendorVerification.REVOKED:
        verification.revoked_at = now
        verification.verified_by = reviewer
    elif status == VendorVerification.SUSPENDED:
        verification.verified_by = reviewer
    verification.status = status
    verification.save()
    if reviewer is not None:
        AuditEvent.objects.create(
            actor=reviewer,
            action=f"vendor.status.{status}",
            object_type="VendorVerification",
            object_id=str(verification.pk),
            metadata={"seller_id": seller.id, "note": str(note or "")[:2000]},
        )
    return verification
