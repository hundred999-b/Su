from marketplace.models import Order
from stage4.models import DisputeEvent
from .models import VendorComplaint, VendorTrustSettings, VendorVerification


def vendor_trust_metrics(seller):
    completed = Order.objects.filter(product__seller=seller, status=Order.COMPLETED).count()
    disputed = (
        DisputeEvent.objects.filter(
            order__product__seller=seller,
            event_type="opened",
        )
        .values("order_id")
        .distinct()
        .count()
    )
    complaints = VendorComplaint.objects.filter(
        seller=seller,
        status__in=[VendorComplaint.OPEN, VendorComplaint.SUBSTANTIATED],
    ).count()
    serious_complaints = VendorComplaint.objects.filter(
        seller=seller,
        status__in=[VendorComplaint.OPEN, VendorComplaint.SUBSTANTIATED],
        severity__in=[VendorComplaint.HIGH, VendorComplaint.CRITICAL],
    ).count()
    dispute_rate = (disputed / completed * 100) if completed else 0
    settings = VendorTrustSettings.get_solo()
    return {
        "completed_transactions": completed,
        "dispute_count": disputed,
        "dispute_rate_percent": round(dispute_rate, 2),
        "open_complaint_count": complaints,
        "serious_complaint_count": serious_complaints,
        "caution_thresholds": {
            "disputes": settings.caution_dispute_threshold,
            "complaints": settings.caution_complaint_threshold,
            "dispute_rate_percent": settings.caution_dispute_rate_percent,
        },
    }


def vendor_has_caution(seller, verification=None):
    verification = verification or VendorVerification.objects.filter(seller=seller).first()
    if verification and verification.caution_override is True:
        return True
    if verification and verification.caution_override is False:
        return False
    metrics = vendor_trust_metrics(seller)
    thresholds = metrics["caution_thresholds"]
    return bool(
        metrics["dispute_count"] >= thresholds["disputes"]
        or metrics["open_complaint_count"] >= thresholds["complaints"]
        or metrics["serious_complaint_count"] > 0
        or metrics["dispute_rate_percent"] >= thresholds["dispute_rate_percent"]
    )


def vendor_caution_reasons(seller, verification=None):
    verification = verification or VendorVerification.objects.filter(seller=seller).first()
    if verification and verification.caution_override is False:
        return []
    metrics = vendor_trust_metrics(seller)
    thresholds = metrics["caution_thresholds"]
    reasons = []
    if metrics["dispute_count"] >= thresholds["disputes"]:
        reasons.append(f"{metrics['dispute_count']} disputes")
    if metrics["open_complaint_count"] >= thresholds["complaints"]:
        reasons.append(f"{metrics['open_complaint_count']} open complaints")
    if metrics["serious_complaint_count"] > 0:
        reasons.append(f"{metrics['serious_complaint_count']} serious complaint(s)")
    if metrics["dispute_rate_percent"] >= thresholds["dispute_rate_percent"]:
        reasons.append(f"{metrics['dispute_rate_percent']}% dispute rate")
    if verification and verification.caution_override is True and verification.caution_note:
        reasons.append(verification.caution_note.strip())
    return reasons


def vendor_badges(seller):
    verification = VendorVerification.objects.filter(seller=seller).first()
    caution = vendor_has_caution(seller, verification)
    reasons = vendor_caution_reasons(seller, verification) if caution else []
    badge = None
    if verification:
        if verification.status == VendorVerification.TRUSTED:
            badge = {"key": "trusted", "label": "Trusted Vendor", "description": "Trusted by ShopU based on seller reliability and admin review."}
        elif verification.status == VendorVerification.VERIFIED:
            badge = {"key": "verified", "label": "Verified Vendor", "description": "Seller completed ShopU's verification process."}
        elif verification.status in (VendorVerification.SUSPENDED, VendorVerification.REVOKED):
            badge = {"key": "caution", "label": "Proceed with caution", "description": "Seller verification is not currently in good standing."}
    return {
        "primary": badge,
        "caution": caution,
        "caution_reasons": reasons,
        "metrics": vendor_trust_metrics(seller),
    }
