"""Management command to compute analytics for exams."""

from django.core.management.base import BaseCommand, CommandError

from apps.analytics.services import compute_all_analytics
from apps.results.models import Exam


class Command(BaseCommand):
    help = "Compute analytics aggregates for exam results"

    def add_arguments(self, parser):
        parser.add_argument(
            "--exam",
            type=str,
            help="Exam code to compute analytics for (if not provided, processes all exams)",
        )
        parser.add_argument(
            "--all",
            action="store_true",
            help="Compute analytics for all exams",
        )

    def handle(self, *args, **options):
        exam_code = options.get("exam")
        all_exams = options.get("all")

        if exam_code:
            # Process specific exam
            try:
                exam = Exam.objects.get(code=exam_code)
            except Exam.DoesNotExist as e:
                raise CommandError(f'Exam with code "{exam_code}" does not exist') from e

            self.stdout.write(f"Computing analytics for exam: {exam.code}")
            result = compute_all_analytics(exam)

            self.stdout.write(
                self.style.SUCCESS(
                    f'✓ Exam aggregate computed: {result["exam_aggregate"].total_students} students'
                )
            )
            self.stdout.write(
                self.style.SUCCESS(
                    f'✓ Component aggregates computed: '
                    f'{len(result["component_aggregates"])} components'
                )
            )
            self.stdout.write(
                self.style.SUCCESS(
                    f'✓ Anomaly flags detected: {len(result["anomaly_flags"])} flags'
                )
            )

        elif all_exams:
            # Process all exams
            exams = Exam.objects.all()
            total = exams.count()

            if total == 0:
                self.stdout.write(self.style.WARNING("No exams found in database"))
                return

            self.stdout.write(f"Computing analytics for {total} exams...")

            success_count = 0
            for exam in exams:
                try:
                    result = compute_all_analytics(exam)
                    success_count += 1
                    self.stdout.write(
                        f'  ✓ {exam.code}: {result["exam_aggregate"].total_students} students'
                    )
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f"  ✗ {exam.code}: {str(e)}"))

            self.stdout.write(
                self.style.SUCCESS(
                    f"\nCompleted: {success_count}/{total} exams processed successfully"
                )
            )

        else:
            raise CommandError("Please specify --exam <code> or --all")
