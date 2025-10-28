"""Management command to backfill result status for legacy data."""

from django.core.management.base import BaseCommand
from django.db.models import Q

from apps.results.models import Result


class Command(BaseCommand):
    """
    Backfill status=PUBLISHED for results with published_at set.

    This command is used to migrate legacy data where results were published
    before the workflow status system was implemented.
    """

    help = "Backfill status=PUBLISHED for results with published_at timestamp"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Preview changes without applying them",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]

        # Find results with published_at but not PUBLISHED status
        results = Result.objects.filter(
            Q(published_at__isnull=False)
            & (
                Q(status=Result.ResultStatus.DRAFT)
                | Q(status=Result.ResultStatus.VERIFIED)
                | Q(status=Result.ResultStatus.SUBMITTED)
            )
        )

        count = results.count()

        if dry_run:
            self.stdout.write(
                self.style.WARNING(f"DRY RUN: Would update {count} results to PUBLISHED status")
            )
            # Show sample of results that would be updated
            for result in results[:10]:
                self.stdout.write(
                    f"  - Result #{result.id}: {result.student.roll_number} - "
                    f"{result.subject} ({result.status} → PUBLISHED)"
                )
            if count > 10:
                self.stdout.write(f"  ... and {count - 10} more")
        else:
            # Update all matching results
            updated = results.update(status=Result.ResultStatus.PUBLISHED)

            self.stdout.write(
                self.style.SUCCESS(f"Successfully updated {updated} results to PUBLISHED status")
            )

        if count == 0:
            self.stdout.write(
                self.style.SUCCESS("No results need to be backfilled. All data is up to date!")
            )
