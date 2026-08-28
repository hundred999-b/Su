from django.db import transaction

from marketplace.models import Order
from stage4.models import DisputeEvent
from .models import Review


def _review_is_eligible(order):
    """A buyer may review a completed trade, or a buyer-favour dispute refund."""
    if order.status == Order.COMPLETED:
        return True
    if order.status != Order.REFUNDED:
        return False
    return DisputeEvent.objects.filter(
        order=order,
        event_type="resolved",
        metadata__outcome="buyer_favor",
    ).exists()


@transaction.atomic
def create_review(*, buyer, order_id, rating, comment=""):
    order = (
        Order.objects
        .select_for_update()
        .select_related("product", "product__seller")
        .get(pk=order_id)
    )

    if order.buyer_id != buyer.id:
        raise ValueError("Only the buyer can review this order.")

    if not _review_is_eligible(order):
        if order.status == Order.DISPUTED:
            raise ValueError(
                "This order is under dispute. You can review the seller "
                "after the dispute is resolved in your favor."
            )
        raise ValueError(
            "A review is only available after a completed trade or a "
            "dispute resolved in the buyer's favor."
        )

    seller = order.product.seller

    if seller_id := getattr(order, "seller_id", None):
        if seller_id != seller.id:
            raise ValueError("Invalid seller relationship.")

    if Review.objects.filter(order=order).exists():
        raise ValueError("This transaction has already been reviewed.")

    return Review.objects.create(
        buyer=buyer,
        seller=seller,
        order=order,
        rating=rating,
        comment=comment.strip(),
    )


@transaction.atomic
def edit_review(*, buyer, review_id, rating, comment=""):
    review = (
        Review.objects
        .select_for_update()
        .get(pk=review_id)
    )

    if review.buyer_id != buyer.id:
        raise ValueError("Only the original buyer can edit this review.")

    review.rating = rating
    review.comment = comment.strip()
    review.edited = True
    review.save(update_fields=[
        "rating",
        "comment",
        "edited",
        "updated_at",
    ])

    return review
