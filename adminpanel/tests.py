from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from .jobs import enqueue_job, claim_job, complete_job, fail_job
from .models import BackgroundJob


class BackgroundJobTests(TestCase):
    def test_enqueue_is_deduplicated(self):
        with patch("adminpanel.jobs.trigger_runner"):
            first, created1 = enqueue_job(
                "test.job", dedupe_key="test:1", payload={"x": 1}
            )
            second, created2 = enqueue_job(
                "test.job", dedupe_key="test:1", payload={"x": 2}
            )
        self.assertTrue(created1)
        self.assertFalse(created2)
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(BackgroundJob.objects.count(), 1)

    def test_claim_only_returns_due_pending_job(self):
        future = timezone.now() + timedelta(hours=1)
        BackgroundJob.objects.create(
            kind="test.future", dedupe_key="test:future", run_after=future
        )
        self.assertIsNone(claim_job())
        BackgroundJob.objects.create(
            kind="test.now", dedupe_key="test:now", run_after=timezone.now()
        )
        job = claim_job()
        self.assertIsNotNone(job)
        self.assertEqual(job.status, BackgroundJob.RUNNING)
        self.assertEqual(job.attempts, 1)

    def test_failed_job_retries_with_backoff(self):
        job = BackgroundJob.objects.create(
            kind="test.retry", dedupe_key="test:retry", run_after=timezone.now()
        )
        claimed = claim_job()
        fail_job(claimed, RuntimeError("temporary"))
        claimed.refresh_from_db()
        self.assertEqual(claimed.status, BackgroundJob.PENDING)
        self.assertEqual(claimed.attempts, 1)
        self.assertTrue(claimed.run_after > timezone.now())

    def test_completion_is_terminal(self):
        job = BackgroundJob.objects.create(
            kind="test.complete", dedupe_key="test:complete", run_after=timezone.now()
        )
        claimed = claim_job()
        complete_job(claimed, result={"ok": True})
        claimed.refresh_from_db()
        self.assertEqual(claimed.status, BackgroundJob.COMPLETED)
        self.assertIsNotNone(claimed.completed_at)
        self.assertEqual(claimed.result, {"ok": True})


class UserAdminPrivilegeTests(TestCase):
    def test_non_superuser_cannot_change_superuser_status(self):
        from django.contrib.auth import get_user_model
        from django.contrib.auth.models import Permission
        from django.test import RequestFactory
        from django.contrib import admin
        from adminpanel.admin import ShopUUserAdmin

        User = get_user_model()
        staff = User.objects.create_user(
            username="staff-rbac",
            password="test-password",
            is_staff=True,
            is_superuser=False,
        )
        target = User.objects.create_user(
            username="target-user",
            password="test-password",
            is_staff=False,
            is_superuser=False,
        )

        permission = Permission.objects.get(
            codename="change_user",
            content_type__app_label=User._meta.app_label,
        )
        staff.user_permissions.add(permission)

        request = RequestFactory().get("/admin/")
        request.user = staff

        admin_obj = ShopUUserAdmin(User, admin.site)
        Form = admin_obj.get_form(request, target)
        form = Form(instance=target)

        self.assertTrue(form.fields["is_superuser"].disabled)
        self.assertTrue(form.fields["is_staff"].disabled)
        self.assertTrue(form.fields["groups"].disabled)
        self.assertTrue(form.fields["user_permissions"].disabled)
