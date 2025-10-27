"""Management command to backfill result status based on published_at."""

from django.core.management.base import BaseCommand
from django.db.models import Q

from apps.results.models import Result


class Command(BaseCommand):
    help = (
        "Backfill result status to PUBLISHED where published_at is set but status is not PUBLISHED"
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be updated without making changes",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]

        # Find results with published_at set but status not PUBLISHED
        results_to_fix = Result.objects.filter(
            Q(published_at__isnull=False) & ~Q(status=Result.ResultStatus.PUBLISHED)
        )

        count = results_to_fix.count()

        if count == 0:
            self.stdout.write(self.style.SUCCESS("No results need status backfill."))
            return

        if dry_run:
            self.stdout.write(
                self.style.WARNING(f"DRY RUN: Would update {count} result(s) to PUBLISHED status:")
            )
            for result in results_to_fix[:10]:  # Show first 10
                self.stdout.write(
                    f"  - {result.student.roll_number} - {result.subject} "
                    f"(current: {result.status}, published_at: {result.published_at})"
                )
            if count > 10:
                self.stdout.write(f"  ... and {count - 10} more")
        else:
            # Update status to PUBLISHED
            results_to_fix.update(status=Result.ResultStatus.PUBLISHED)
            self.stdout.write(
                self.style.SUCCESS(f"Successfully updated {count} result(s) to PUBLISHED status.")
            )
