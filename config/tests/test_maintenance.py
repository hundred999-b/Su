from datetime import timedelta
from unittest.mock import patch

from django.test import Client, TestCase, override_settings
from django.utils import timezone

from adminpanel.models import MaintenanceLease


@override_settings(SHOPU_CRON_SECRET="test-cron-secret", SECURE_SSL_REDIRECT=False)
class MaintenanceEndpointTests(TestCase):
    url = "/api/maintenance/auto-release/"

    def setUp(self):
        self.client = Client()

    def test_missing_secret_is_rejected(self):
        response = self.client.post(self.url)

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["error"], "Unauthorized")

    def test_wrong_secret_is_rejected(self):
        response = self.client.post(
            self.url,
            HTTP_X_SHOPU_CRON_SECRET="wrong-secret",
        )

        self.assertEqual(response.status_code, 401)

    @patch("config.maintenance._run_maintenance")
    def test_valid_secret_runs_maintenance_and_releases_lease(
        self,
        mock_run,
    ):
        mock_run.return_value = (
            {
                "escrow_discovery": True,
                "jobs_processed": 2,
                "support": {"expired": [], "matched": []},
            },
            [],
        )

        response = self.client.post(
            self.url,
            HTTP_X_SHOPU_CRON_SECRET="test-cron-secret",
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["success"])
        self.assertEqual(response.json()["jobs_processed"], 2)
        mock_run.assert_called_once()

        lease = MaintenanceLease.objects.get(pk=1)

        self.assertIsNone(lease.locked_until)
        self.assertIsNotNone(lease.last_started_at)
        self.assertIsNotNone(lease.last_finished_at)

    def test_active_lease_skips_second_worker(self):
        now = timezone.now()

        MaintenanceLease.objects.create(
            pk=1,
            locked_until=now + timedelta(seconds=60),
            last_started_at=now,
        )

        with patch(
            "config.maintenance._run_maintenance"
        ) as mock_run:
            response = self.client.post(
                self.url,
                HTTP_X_SHOPU_CRON_SECRET="test-cron-secret",
            )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["success"])
        self.assertIn("skipped", response.json())
        mock_run.assert_not_called()

    @patch("config.maintenance._run_maintenance")
    def test_maintenance_errors_return_207_and_release_lease(
        self,
        mock_run,
    ):
        mock_run.return_value = (
            {
                "escrow_discovery": False,
                "jobs_processed": 0,
            },
            ["escrow discovery: test failure"],
        )

        response = self.client.post(
            self.url,
            HTTP_X_SHOPU_CRON_SECRET="test-cron-secret",
        )

        self.assertEqual(response.status_code, 207)
        self.assertFalse(response.json()["success"])
        self.assertEqual(
            response.json()["errors"],
            ["escrow discovery: test failure"],
        )

        lease = MaintenanceLease.objects.get(pk=1)

        self.assertIsNone(lease.locked_until)
        self.assertIsNotNone(lease.last_finished_at)

    @patch("config.maintenance.process_pending_jobs")
    @patch("escrow.automation.run_auto_release")
    @patch("support.services.run_support_maintenance")
    def test_run_maintenance_runs_all_three_components(
        self,
        mock_support,
        mock_escrow,
        mock_jobs,
    ):
        mock_escrow.return_value = None
        mock_jobs.return_value = (3, [])
        mock_support.return_value = {
            "expired": [1],
            "matched": [2],
        }

        from config.maintenance import _run_maintenance

        result, errors = _run_maintenance()

        self.assertEqual(
            result,
            {
                "escrow_discovery": True,
                "jobs_processed": 3,
                "support": {
                    "expired": [1],
                    "matched": [2],
                },
            },
        )
        self.assertEqual(errors, [])

        mock_escrow.assert_called_once()
        mock_jobs.assert_called_once_with(limit=25)
        mock_support.assert_called_once()
