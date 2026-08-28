from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.utils import timezone

from .models import Product, ListingPolicy, ListingVersion, Order

DEFAULT_POLICY = """By publishing a listing, the seller confirms that the information is accurate and complete to the best of their knowledge, including material defects, limitations, missing parts/accessories, condition, compatibility and other facts a reasonable buyer would need to make an informed decision. The seller agrees to ShopU marketplace rules and applicable fees. Misleading, fraudulent or materially incomplete listings may be subject to moderation, refunds, disputes or account action."""


def get_active_listing_policy():
    policy = ListingPolicy.objects.filter(
        key="seller_listing_terms", active=True
    ).order_by("-version").first()
    if policy:
        return policy
    return ListingPolicy.objects.create(
        key="seller_listing_terms",
        version=1,
        title="Seller Listing Terms",
        content=DEFAULT_POLICY,
        active=True,
    )


def validate_listing_data(data):
    title = str(data.get("title", "")).strip()
    description = str(data.get("description", "")).strip()
    price = data.get("price")
    if len(title) < 3:
        raise ValueError("Title must contain at least 3 characters.")
    if len(description) < 30:
        raise ValueError(
            "Please provide a full description (at least 30 characters). "
            "Include condition, known defects, limitations and included items."
        )
    if price is None:
        raise ValueError("Price is required.")
    try:
        if Decimal(str(price)) <= 0:
            raise ValueError("Price must be greater than zero.")
    except InvalidOperation:
        raise ValueError("Price must be a valid number.")
    currency = str(data.get("currency", "USD")).strip().upper()
    if not currency or len(currency) > 10:
        raise ValueError("A valid currency is required.")
    if not data.get("disclosure_acknowledged"):
        raise ValueError(
            "You must confirm that the listing fully discloses known material details."
        )
    if not data.get("fee_acknowledged"):
        raise ValueError(
            "You must accept the applicable ShopU fees and seller terms."
        )
    return title, description


@transaction.atomic
def publish_listing(*, seller, data, product=None):
    title, description = validate_listing_data(data)

    from stage4.models import TermsDocument
    from stage4.services import require_terms, record_listing_version

    seller_terms_document = require_terms(
        seller,
        TermsDocument.SELLER,
        purpose="listing",
    )
    seller_custom_terms = str(data.get("seller_terms", "")).strip()
    if not seller_custom_terms:
        raise ValueError("Seller-specific listing terms are required.")

    policy = get_active_listing_policy()
    now = timezone.now()

    if product is None:
        product = Product.objects.create(
            seller=seller,
            title=title,
            description=description,
            category=str(data.get("category", "")).strip(),
            condition=str(data.get("condition", "")).strip(),
            specifications=data.get("specifications") or {},
            seller_terms=seller_custom_terms,
            price=data["price"],
            currency=str(data.get("currency", "USD")).upper(),
            image=data.get("image"),
        )
    else:
        product = Product.objects.select_for_update().get(pk=product.pk)
        if product.seller_id != seller.id:
            raise ValueError("You cannot edit another seller's listing.")
        product.title = title
        product.description = description
        product.category = str(data.get("category", "")).strip()
        product.condition = str(data.get("condition", "")).strip()
        product.specifications = data.get("specifications") or {}
        product.seller_terms = seller_custom_terms
        product.price = data["price"]
        product.currency = str(data.get("currency", "USD")).upper()
        if data.get("image") is not None:
            product.image = data["image"]
        product.version += 1

    product.disclosure_acknowledged = True
    product.fee_acknowledged = True
    product.listing_policy_version = policy.version
    product.listing_policy_content = policy.content
    product.published_at = now
    product.active = True
    product.save()

    # Stage 4 is the authoritative legal/evidence listing version.
    record_listing_version(
        product,
        seller_terms=seller_terms_document,
        accuracy_confirmed=True,
        fee_disclosed=True,
        metadata={
            "seller_custom_terms": seller_custom_terms,
            "listing_policy_version": policy.version,
            "listing_policy_content": policy.content,
        },
    )

    # Keep the legacy marketplace version synchronized for old read-only
    # integrations. New orders do not use it as their evidence source.
    ListingVersion.objects.update_or_create(
        product=product,
        version=product.version,
        defaults={
            "title": product.title,
            "description": product.description,
            "category": product.category,
            "condition": product.condition,
            "specifications": product.specifications,
            "seller_terms": product.seller_terms,
            "price": product.price,
            "currency": product.currency,
            "policy_version": policy.version,
            "policy_content": policy.content,
            "seller_acknowledged_at": now,
        },
    )
    return product


def snapshot_for_order(product):
    """Legacy compatibility helper; ensures Stage 4 evidence also exists."""
    from stage4.services import ensure_listing_version

    product = Product.objects.get(pk=product.pk)
    stage4_version = ensure_listing_version(product)

    return ListingVersion.objects.update_or_create(
        product=product,
        version=stage4_version.version,
        defaults={
            "title": stage4_version.title,
            "description": stage4_version.description,
            "category": stage4_version.category,
            "condition": product.condition,
            "specifications": product.specifications,
            "seller_terms": product.seller_terms,
            "price": stage4_version.price,
            "currency": stage4_version.currency,
            "policy_version": product.listing_policy_version,
            "policy_content": product.listing_policy_content,
            "seller_acknowledged_at": product.published_at,
        },
    )[0]


@transaction.atomic
def purchase_product(*, buyer, product_id, disclosure_acknowledged=True, idempotency_key=None):
    """The single marketplace purchase path used by every entry point."""
    from stage4.models import TermsDocument
    from stage4.services import require_terms, snapshot_order

    if idempotency_key:
        idempotency_key = str(idempotency_key).strip()
        if len(idempotency_key) > 120:
            raise ValueError("Idempotency key is too long.")
        existing = (
            Order.objects.select_for_update()
            .filter(buyer=buyer, idempotency_key=idempotency_key)
            .first()
        )
        if existing:
            if not hasattr(existing, "escrow"):
                raise ValueError("An incomplete idempotent order exists.")
            from ledger.models import LedgerTransaction
            tx = LedgerTransaction.objects.get(
                transaction_id=existing.escrow.funding_transaction_id
            )
            existing._idempotent_replay = True
            return existing, tx

    if not disclosure_acknowledged:
        raise ValueError(
            "You must confirm that you reviewed the full listing description "
            "and disclosed condition before buying."
        )

    require_terms(buyer, TermsDocument.BUYER, purpose="purchase")

    product = (
        Product.objects.select_for_update()
        .select_related("seller")
        .filter(pk=product_id, active=True)
        .first()
    )
    if not product:
        raise ValueError("Product not found.")
    if product.seller_id == buyer.id:
        raise ValueError("You cannot purchase your own product.")

    order = Order.objects.create(
        buyer=buyer,
        product=product,
        idempotency_key=idempotency_key,
        amount=product.price,
        currency=product.currency,
        status=Order.PENDING,
        buyer_disclosure_acknowledged_at=timezone.now(),
    )

    snapshot = snapshot_order(order)
    order.listing_version = snapshot.listing_version.version
    order.product_title_snapshot = snapshot.title
    order.description_snapshot = snapshot.description
    order.condition_snapshot = snapshot.product.condition
    order.specifications_snapshot = snapshot.product.specifications
    order.seller_terms_snapshot = snapshot.listing_version.metadata.get(
        "seller_custom_terms", snapshot.product.seller_terms
    )
    order.policy_version_snapshot = product.listing_policy_version
    order.policy_content_snapshot = product.listing_policy_content
    order.save(
        update_fields=[
            "listing_version",
            "product_title_snapshot",
            "description_snapshot",
            "condition_snapshot",
            "specifications_snapshot",
            "seller_terms_snapshot",
            "policy_version_snapshot",
            "policy_content_snapshot",
        ]
    )

    from ledger.transaction_service import purchase_order
    tx = purchase_order(order)
    return order, tx


@transaction.atomic
def mark_order_delivered(*, order_id, seller, auto_release_hours):
    order = (
        Order.objects.select_for_update()
        .select_related("product", "buyer")
        .filter(
            pk=order_id,
            product__seller=seller,
            status=Order.ESCROW,
        )
        .first()
    )
    if not order:
        raise ValueError("Order not found or not in escrow.")

    order.status = Order.DELIVERED
    order.delivered_at = timezone.now()
    order.set_deadline(auto_release_hours)
    order.save(
        update_fields=["status", "delivered_at", "confirmation_deadline"]
    )
    from adminpanel.jobs import enqueue_job
    enqueue_job(
        "escrow.auto_release",
        dedupe_key=f"escrow:auto-release:order:{order.pk}",
        payload={"order_id": order.pk},
        run_after=order.confirmation_deadline,
    )
    return order


@transaction.atomic
def confirm_order(*, order_id, buyer):
    """Buyer confirmation is a business action, not an admin settlement permission."""
    from escrow.models import Escrow
    from escrow.services import settle_escrow_for_buyer

    order = (
        Order.objects.select_for_update()
        .select_related("product", "product__seller")
        .filter(pk=order_id, buyer=buyer, status=Order.DELIVERED)
        .first()
    )
    if not order:
        raise ValueError("Order must be delivered before you can confirm it.")

    if (
        order.confirmation_deadline
        and timezone.now() > order.confirmation_deadline
    ):
        raise ValueError("The confirmation window has expired.")

    escrow = Escrow.objects.select_for_update().get(order=order)
    tx = settle_escrow_for_buyer(
        escrow.id, buyer=buyer, reason="buyer_confirmed"
    )
    return order, tx


@transaction.atomic
def open_dispute(*, order_id, actor, message="Buyer/seller opened a dispute."):
    from escrow.models import Escrow
    from stage4.models import DisputeEvent

    order = (
        Order.objects.select_for_update()
        .select_related("product", "buyer")
        .filter(
            pk=order_id,
            status__in=[Order.ESCROW, Order.DELIVERED],
        )
        .filter(
            buyer=actor,
        )
        .first()
    )
    if not order:
        # Sellers can also raise a dispute, but only for their own orders.
        order = (
            Order.objects.select_for_update()
            .select_related("product", "buyer")
            .filter(
                pk=order_id,
                status__in=[Order.ESCROW, Order.DELIVERED],
                product__seller=actor,
            )
            .first()
        )
    if not order:
        raise ValueError("Order not found or you are not a participant.")

    escrow = Escrow.objects.select_for_update().filter(
        order=order, status=Escrow.HOLDING
    ).first()
    if not escrow:
        raise ValueError("This order is no longer eligible for dispute.")

    escrow.status = Escrow.DISPUTED
    escrow.save(update_fields=["status"])
    order.status = Order.DISPUTED
    order.save(update_fields=["status"])

    event = DisputeEvent.objects.create(
        order=order,
        actor=actor,
        event_type="opened",
        message=message.strip()[:5000],
        metadata={"escrow_id": escrow.id},
    )
    return order, event
