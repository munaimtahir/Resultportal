"""Management command to import students from CSV file."""

import sys
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from apps.accounts.importers import StudentCSVImporter


class Command(BaseCommand):
    help = "Import students from CSV file"

    def add_arguments(self, parser):
        parser.add_argument("csv_file", type=str, help="Path to the CSV file")
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Preview changes without committing them",
        )
        parser.add_argument(
            "--commit",
            action="store_true",
            help="Commit changes to the database",
        )
        parser.add_argument(
            "--notes",
            type=str,
            default="",
            help="Optional notes for the import batch",
        )

    def handle(self, *args, **options):
        csv_file = options["csv_file"]
        dry_run = options["dry_run"]
        commit = options["commit"]
        notes = options["notes"]

        # Default to dry-run if neither --dry-run nor --commit is specified
        if not dry_run and not commit:
            dry_run = True
            self.stdout.write(self.style.WARNING("No mode specified, defaulting to --dry-run"))

        if dry_run and commit:
            raise CommandError("Cannot specify both --dry-run and --commit")

        # Validate file exists
        file_path = Path(csv_file)
        if not file_path.exists():
            raise CommandError(f"File does not exist: {csv_file}")

        # Get current user (for audit trail)
        User = get_user_model()
        try:
            # Try to get a staff user for system imports
            user = User.objects.filter(is_staff=True).first()
            if not user:
                # Create a system user if none exists
                user = User.objects.create_user(
                    username="system",
                    email="system@pmc.edu.pk",
                    is_staff=True,
                )
        except Exception:
            user = None

        # Process the import
        try:
            with open(file_path, encoding="utf-8") as f:
                importer = StudentCSVImporter(
                    f,
                    started_by=user,
                    filename=file_path.name,
                    notes=notes,
                )

                if dry_run:
                    self.stdout.write("Running in DRY-RUN mode...")
                    summary = importer.preview()
                else:
                    self.stdout.write("Running in COMMIT mode...")
                    summary = importer.commit()

                # Print summary
                self.stdout.write(f"File: {csv_file}")
                self.stdout.write(f"Total rows processed: {summary.row_count}")
                self.stdout.write(self.style.SUCCESS(f"Created: {summary.created}"))
                self.stdout.write(self.style.WARNING(f"Updated: {summary.updated}"))
                self.stdout.write(self.style.ERROR(f"Skipped: {summary.skipped}"))

                # Show errors if any
                if summary.skipped > 0:
                    self.stdout.write("\nErrors found:")
                    for row_result in summary.row_results:
                        if row_result.has_errors:
                            self.stdout.write(
                                f"  Row {row_result.row_number}: {'; '.join(row_result.errors)}"
                            )

                # Exit with non-zero status if there were errors
                if summary.skipped > 0:
                    sys.exit(1)

        except Exception as e:
            raise CommandError(f"Import failed: {str(e)}")
