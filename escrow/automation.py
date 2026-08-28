from django.utils import timezone

from escrow.models import Escrow, PrivateEscrow
from escrow.services import _release_escrow_internal, _release_private_escrow_internal
from marketplace.models import Order
from telegram_integration.models import Notification


def _release_order(order_id):
    order = Order.objects.select_related("product", "product__seller", "buyer").get(pk=order_id)
    if order.status != Order.DELIVERED:
        return False
    if not order.confirmation_deadline or order.confirmation_deadline > timezone.now():
        return False
    escrow = Escrow.objects.filter(order=order, status=Escrow.HOLDING).first()
    if not escrow:
        return False
    _release_escrow_internal(escrow, reason="inspection_window_expired")
    Notification.objects.create(
        user=order.buyer,
        kind="escrow",
        title="Order auto-settled",
        message=f"Order #{order.id} passed the inspection window and was automatically settled.",
    )
    Notification.objects.create(
        user=order.product.seller,
        kind="escrow",
        title="Funds released",
        message=f"Order #{order.id} passed the inspection window and funds were released.",
    )
    return True


def _release_private(escrow_id):
    escrow = PrivateEscrow.objects.select_related("seller", "buyer").get(escrow_id=escrow_id)
    if escrow.status != PrivateEscrow.DELIVERED:
        return False
    if not escrow.deadline or escrow.deadline > timezone.now():
        return False
    _release_private_escrow_internal(escrow, reason="inspection_window_expired")
    Notification.objects.create(
        user=escrow.seller,
        kind="escrow",
        title="Private escrow auto-settled",
        message=f"{escrow.escrow_id} passed its inspection window and was released.",
    )
    return True


def process_job(job):
    """Dispatch one database job. Add new job kinds here as background features grow."""
    kind = job.kind
    payload = job.payload or {}
    if kind == "escrow.auto_release":
        if payload.get("private_escrow_id"):
            done = _release_private(payload["private_escrow_id"])
        else:
            done = _release_order(payload.get("order_id"))
        return {"released": bool(done), "job": kind}
    raise ValueError(f"Unknown background job kind: {kind}")


def run_auto_release():
    """Compatibility command: enqueue due/missing escrow jobs, then process jobs.

    New deployments should rely on event-created jobs. This compatibility path is
    intentionally bounded and only exists so old delivered records are not stranded.
    """
    from adminpanel.jobs import enqueue_job, process_pending_jobs

    now = timezone.now()
    for order in Order.objects.filter(status=Order.DELIVERED, confirmation_deadline__isnull=False, confirmation_deadline__lte=now):
        enqueue_job(
            "escrow.auto_release",
            dedupe_key=f"escrow:auto-release:order:{order.pk}",
            payload={"order_id": order.pk},
            run_after=order.confirmation_deadline,
        )
    for escrow in PrivateEscrow.objects.filter(status=PrivateEscrow.DELIVERED, deadline__isnull=False, deadline__lte=now):
        enqueue_job(
            "escrow.auto_release",
            dedupe_key=f"escrow:auto-release:private:{escrow.escrow_id}",
            payload={"private_escrow_id": escrow.escrow_id},
            run_after=escrow.deadline,
        )
    return None
