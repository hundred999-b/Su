"""Small, database-backed event-driven job queue.

Jobs are created by business events.  The external runner is only a trigger;
the database is the source of truth, so retries are safe and no work is lost
when Render restarts or sleeps.
"""
import logging
from datetime import timedelta

import requests
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .models import BackgroundJob

logger = logging.getLogger(__name__)


def enqueue_job(kind, *, dedupe_key, payload=None, run_after=None, max_attempts=5):
    """Create/revive one job and notify the external runner after commit."""
    run_after = run_after or timezone.now()
    with transaction.atomic():
        job, created = BackgroundJob.objects.select_for_update().get_or_create(
            dedupe_key=dedupe_key,
            defaults={
                "kind": kind,
                "payload": payload or {},
                "run_after": run_after,
                "max_attempts": max_attempts,
            },
        )
        if not created and job.status == BackgroundJob.FAILED and job.attempts < job.max_attempts:
            job.status = BackgroundJob.PENDING
            job.run_after = run_after
            job.last_error = ""
            job.save(update_fields=["status", "run_after", "last_error", "updated_at"])
        transaction.on_commit(trigger_runner)
        return job, created


def trigger_runner():
    """Ask GitHub Actions to run immediately when configured.

    Failure to notify the runner never rolls back the business transaction;
    the low-frequency safety scheduler can pick up the pending job later.
    """
    token = getattr(settings, "SHOPU_GITHUB_ACTIONS_TOKEN", "")
    repository = getattr(settings, "SHOPU_GITHUB_REPOSITORY", "")
    event_type = getattr(settings, "SHOPU_GITHUB_EVENT_TYPE", "shopu-job")
    if not token or not repository:
        return False
    url = f"https://api.github.com/repos/{repository}/dispatches"
    try:
        response = requests.post(
            url,
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {token}",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            json={"event_type": event_type},
            timeout=5,
        )
        response.raise_for_status()
        return True
    except requests.RequestException as exc:
        logger.warning("Unable to trigger GitHub maintenance runner: %s", exc)
        return False


def claim_job():
    """Atomically claim one due job; safe with the maintenance lease."""
    now = timezone.now()
    with transaction.atomic():
        # Recover jobs abandoned by a crashed worker.
        # A RUNNING job whose lease has expired is safe to retry.
        BackgroundJob.objects.filter(
            status=BackgroundJob.RUNNING,
            locked_until__isnull=False,
            locked_until__lte=now,
        ).update(
            status=BackgroundJob.PENDING,
            locked_until=None,
        )

        job = (
            BackgroundJob.objects.select_for_update()
            .filter(status=BackgroundJob.PENDING, run_after__lte=now)
            .filter(locked_until__isnull=True)
            .order_by("run_after", "id")
            .first()
        )
        if not job:
            return None
        job.status = BackgroundJob.RUNNING
        job.attempts += 1
        job.locked_until = now + timedelta(minutes=10)
        job.started_at = now
        job.save(update_fields=["status", "attempts", "locked_until", "started_at", "updated_at"])
        return job


def complete_job(job, *, result=None):
    job.status = BackgroundJob.COMPLETED
    job.completed_at = timezone.now()
    job.locked_until = None
    job.result = result or {}
    job.last_error = ""
    job.save(update_fields=["status", "completed_at", "locked_until", "result", "last_error", "updated_at"])


def fail_job(job, exc):
    now = timezone.now()
    job.locked_until = None
    job.last_error = str(exc)[:5000]
    if job.attempts >= job.max_attempts:
        job.status = BackgroundJob.FAILED
    else:
        job.status = BackgroundJob.PENDING
        # Exponential retry backoff, capped at 30 minutes.
        delay = min(30, 2 ** max(0, job.attempts - 1))
        job.run_after = now + timedelta(minutes=delay)
    job.save(update_fields=["status", "locked_until", "last_error", "run_after", "updated_at"])


def process_pending_jobs(limit=25):
    """Process only jobs that actually exist and are due."""
    from escrow.automation import process_job

    processed = 0
    errors = []
    for _ in range(limit):
        job = claim_job()
        if not job:
            break
        try:
            result = process_job(job)
            complete_job(job, result=result or {})
            processed += 1
        except Exception as exc:
            fail_job(job, exc)
            errors.append(f"job {job.id}: {exc}")
    return processed, errors
