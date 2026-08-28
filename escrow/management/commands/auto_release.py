from django.core.management.base import BaseCommand

from escrow.automation import run_auto_release
from adminpanel.jobs import process_pending_jobs


class Command(BaseCommand):
    help = "Enqueue and process delivered escrows whose inspection windows have expired."

    def handle(self, *args, **kwargs):
        run_auto_release()

        count, errors = process_pending_jobs()

        for error in errors:
            self.stderr.write(error)

        if errors:
            self.stdout.write(
                self.style.WARNING(
                    f"Processed {count} job(s) with {len(errors)} error(s)."
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Processed {count} escrow job(s)."
                )
            )
