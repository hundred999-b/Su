from django.db import transaction
from django.utils import timezone

from .models import (
    TermsDocument,
    TermsAcceptance,
    ListingRule,
    ListingVersion,
    OrderListingSnapshot,
    NotificationDelivery,
    DisputeEvent,
)


def client_meta(request):
    return {
        "ip_address": request.META.get("REMOTE_ADDR"),
        "user_agent": request.META.get("HTTP_USER_AGENT", "")[:2000],
    }


def active_terms(kind):
    return (
        TermsDocument.objects.filter(kind=kind, active=True)
        .order_by("-created_at")
        .first()
    )


def require_terms(user, kind, request=None, purpose="general"):
    terms = active_terms(kind)
    if not terms:
        raise ValueError(f"No active {kind} terms are configured")
    if not TermsAcceptance.objects.filter(
        user=user, terms=terms, purpose=purpose
    ).exists():
        raise PermissionError(
            f"Acceptance of {terms.title} version {terms.version} is required"
        )
    return terms


@transaction.atomic
def accept_terms(user, terms, request=None, purpose="general"):
    meta = client_meta(request) if request else {}
    acceptance, _ = TermsAcceptance.objects.get_or_create(
        user=user,
        terms=terms,
        purpose=purpose,
        defaults=meta,
    )
    return acceptance


def validate_listing_data(
    title,
    description,
    accuracy_confirmed=False,
    fee_disclosed=False,
    seller_terms=None,
):
    rules = ListingRule.get_solo()
    title = (title or "").strip()
    description = (description or "").strip()
    seller_terms = (
        seller_terms.strip() if isinstance(seller_terms, str) else seller_terms
    )

    if not title:
        raise ValueError("Listing title is required")
    if len(description) < rules.min_description_chars:
        raise ValueError(
            f"Description must contain at least {rules.min_description_chars} characters"
        )
    if len(description) > rules.max_description_chars:
        raise ValueError(
            f"Description cannot exceed {rules.max_description_chars} characters"
        )

    lowered = description.lower()
    for word in rules.prohibited_keywords:
        if str(word).lower() in lowered:
            raise ValueError("Listing contains prohibited content")

    if rules.require_accuracy_confirmation and not accuracy_confirmed:
        raise ValueError(
            "Seller must confirm that the description is accurate and complete"
        )
    if not fee_disclosed:
        raise ValueError("Seller must acknowledge the displayed marketplace fee")
    if rules.require_seller_terms and not seller_terms:
        raise ValueError(
            "Seller must provide and accept seller-specific listing terms"
        )
    return title, description


@transaction.atomic
def record_listing_version(
    product,
    seller_terms=None,
    accuracy_confirmed=True,
    fee_disclosed=True,
    metadata=None,
):
    last = product.stage4_versions.select_for_update().order_by("-version").first()
    version_number = max(
        product.version,
        (last.version + 1) if last else 1,
    )

    terms_document = seller_terms
    if isinstance(seller_terms, str) or seller_terms is None:
        terms_document = active_terms(TermsDocument.SELLER)

    existing = ListingVersion.objects.filter(
        product=product, version=version_number
    ).first()
    if existing:
        return existing

    return ListingVersion.objects.create(
        product=product,
        version=version_number,
        title=product.title,
        description=product.description,
        category=product.category,
        price=product.price,
        currency=product.currency,
        seller_terms=terms_document,
        accuracy_confirmed=accuracy_confirmed,
        fee_disclosed=fee_disclosed,
        metadata=metadata or {},
    )


@transaction.atomic
def ensure_listing_version(product):
    version = (
        product.stage4_versions.select_for_update()
        .order_by("-version")
        .first()
    )
    if version and version.version >= product.version:
        return version

    return record_listing_version(product)


@transaction.atomic
def snapshot_order(order):
    try:
        return order.stage4_listing_snapshot
    except OrderListingSnapshot.DoesNotExist:
        pass

    version = ensure_listing_version(order.product)
    return OrderListingSnapshot.objects.create(
        order=order,
        product=order.product,
        listing_version=version,
        title=version.title,
        description=version.description,
        category=version.category,
        price=version.price,
        currency=version.currency,
    )


@transaction.atomic
def record_dispute_event(order, actor, event_type, message, metadata=None):
    return DisputeEvent.objects.create(
        order=order,
        actor=actor,
        event_type=event_type,
        message=(message or "")[:5000],
        metadata=metadata or {},
    )


def queue_telegram_notification(notification):
    delivery, _ = NotificationDelivery.objects.get_or_create(
        notification=notification
    )
    return delivery
