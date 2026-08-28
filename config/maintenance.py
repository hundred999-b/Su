import hmac
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_POST

from adminpanel.models import MaintenanceLease
from adminpanel.jobs import process_pending_jobs


def _acquire_lease():
    now = timezone.now()

    with transaction.atomic():
        lease, _ = MaintenanceLease.objects.select_for_update().get_or_create(pk=1)

        if lease.locked_until and lease.locked_until > now:
            return None

        lease.locked_until = now + timedelta(seconds=110)
        lease.last_started_at = now
        lease.save(
            update_fields=[
                "locked_until",
                "last_started_at",
                "updated_at",
            ]
        )
        return lease


def _run_maintenance():
    """
    Central ShopU maintenance cycle.

    All periodic/background maintenance is executed from this single
    entry point. External schedulers only wake this endpoint.
    """
    errors = []
    result = {}

    # 1. Discover/enqueue overdue escrow jobs.
    try:
        from escrow.automation import run_auto_release

        run_auto_release()
        result["escrow_discovery"] = True
    except Exception as exc:
        result["escrow_discovery"] = False
        errors.append(f"escrow discovery: {exc}")

    # 2. Process database-backed background jobs.
    try:
        processed, job_errors = process_pending_jobs(limit=25)
        result["jobs_processed"] = processed
        errors.extend(job_errors)
    except Exception as exc:
        result["jobs_processed"] = 0
        errors.append(f"background jobs: {exc}")

    # 3. Support queue/expiry maintenance.
    try:
        from support.services import run_support_maintenance

        result["support"] = run_support_maintenance()
    except Exception as exc:
        result["support"] = {"error": str(exc)}
        errors.append(f"support maintenance: {exc}")

    return result, errors


@require_POST
def auto_release(request):
    """
    Central authenticated ShopU scheduler endpoint.

    cron-job.org and GitHub Actions both call this endpoint.
    The database lease prevents overlapping executions.
    """
    configured = getattr(settings, "SHOPU_CRON_SECRET", "")
    supplied = request.headers.get("X-ShopU-Cron-Secret", "")

    if not configured or not hmac.compare_digest(supplied, configured):
        return JsonResponse({"error": "Unauthorized"}, status=401)

    lease = _acquire_lease()

    if lease is None:
        return JsonResponse(
            {
                "success": True,
                "skipped": "another maintenance worker is already running",
            },
            status=200,
        )

    try:
        result, errors = _run_maintenance()

        now = timezone.now()

        final_result = {
            **result,
            "errors": errors,
            "finished_at": now.isoformat(),
        }

        lease.last_result = final_result
        lease.last_finished_at = now
        lease.locked_until = None
        lease.save(
            update_fields=[
                "last_result",
                "last_finished_at",
                "locked_until",
                "updated_at",
            ]
        )

        return JsonResponse(
            {
                "success": not bool(errors),
                **final_result,
            },
            status=200 if not errors else 207,
        )

    except Exception as exc:
        now = timezone.now()

        lease.last_result = {
            "errors": [str(exc)],
            "finished_at": now.isoformat(),
        }
        lease.last_finished_at = now
        lease.locked_until = None
        lease.save(
            update_fields=[
                "last_result",
                "last_finished_at",
                "locked_until",
                "updated_at",
            ]
        )

        raise
