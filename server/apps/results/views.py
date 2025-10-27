"""Views for the results app."""

import io

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.generic import FormView, ListView, TemplateView

from apps.accounts.importers import StudentCSVImporter
from apps.accounts.models import YearClass

from .forms import ResultCSVUploadForm, StudentCSVUploadForm
from .importers import ResultCSVImporter
from .models import Exam, ImportBatch, Result


class HomeView(TemplateView):
    """Home page view."""

    template_name = "results/home.html"

    def get(self, request, *args, **kwargs):
        # If user is authenticated and has a student profile, redirect to their profile
        if request.user.is_authenticated and hasattr(request.user, "student_profile"):
            return redirect("results:student_profile")
        return super().get(request, *args, **kwargs)


class StudentProfileView(LoginRequiredMixin, TemplateView):
    """Student profile page showing basic information."""

    template_name = "results/student_profile.html"
    login_url = "accounts:login"

    def get(self, request, *args, **kwargs):
        # Ensure user has a student profile
        if not hasattr(request.user, "student_profile") or not request.user.student_profile:
            messages.error(request, "Student profile not found. Please contact the administrator.")
            return redirect("results:home")
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        student = self.request.user.student_profile
        context["student"] = student
        context["published_results_count"] = (
            Result.objects.published().filter(student=student).count()
        )
        return context


class StudentResultsView(LoginRequiredMixin, ListView):
    """Student results page showing only their own results."""

    template_name = "results/student_results.html"
    context_object_name = "results"
    login_url = "accounts:login"
    paginate_by = 20

    def get(self, request, *args, **kwargs):
        # Ensure user has a student profile
        if not hasattr(request.user, "student_profile") or not request.user.student_profile:
            messages.error(request, "Student profile not found. Please contact the administrator.")
            return redirect("results:home")
        return super().get(request, *args, **kwargs)

    def get_queryset(self):
        """Return only published results for the authenticated student."""
        student = self.request.user.student_profile
        return Result.objects.published().filter(student=student).order_by("-exam_date", "subject")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["student"] = self.request.user.student_profile
        return context


class StaffRequiredMixin(UserPassesTestMixin):
    """Mixin to require staff permissions."""

    def test_func(self):
        return self.request.user.is_authenticated and self.request.user.is_staff


class StudentCSVUploadView(StaffRequiredMixin, FormView):
    """Upload student CSV and show dry-run preview."""

    template_name = "results/import/upload_students.html"
    form_class = StudentCSVUploadForm

    def form_valid(self, form):
        """Process the uploaded CSV in dry-run mode."""
        csv_file = form.cleaned_data["csv_file"]
        year_class = form.cleaned_data["year_class"]

        # Read and decode the file
        content = csv_file.read().decode("utf-8")
        stream = io.StringIO(content)

        # Run the importer in preview mode
        importer = StudentCSVImporter(
            stream,
            started_by=self.request.user,
            filename=csv_file.name,
        )

        try:
            summary = importer.preview()

            # Extract roll numbers from the CSV for later year_class assignment
            stream_for_parsing = io.StringIO(content)
            import csv

            reader = csv.DictReader(stream_for_parsing)
            roll_numbers = [row.get("roll_no", "").strip() for row in reader if row.get("roll_no")]
        except ValueError as e:
            messages.error(self.request, str(e))
            return self.form_invalid(form)

        # Store preview data in session for next step
        self.request.session["import_preview"] = {
            "type": "students",
            "batch_id": summary.batch.id,
            "year_class_id": year_class.id,
            "filename": csv_file.name,
            "content": content,
            "roll_numbers": roll_numbers,
        }

        return redirect("results:student_csv_preview")


class StudentCSVPreviewView(StaffRequiredMixin, TemplateView):
    """Preview student CSV import results and allow submission."""

    template_name = "results/import/preview_students.html"

    def get(self, request, *args, **kwargs):
        """Show preview of import results."""
        preview_data = request.session.get("import_preview")
        if not preview_data or preview_data["type"] != "students":
            messages.error(request, "No preview data found. Please upload a file first.")
            return redirect("results:student_csv_upload")

        batch = ImportBatch.objects.get(id=preview_data["batch_id"])
        year_class = YearClass.objects.get(id=preview_data["year_class_id"])

        context = self.get_context_data(**kwargs)
        context["batch"] = batch
        context["year_class"] = year_class
        context["errors"] = batch.errors_json
        context["warnings"] = batch.warnings_json

        return render(request, self.template_name, context)

    def post(self, request, *args, **kwargs):
        """Submit the import for real."""
        preview_data = request.session.get("import_preview")
        if not preview_data or preview_data["type"] != "students":  # pragma: no cover - defensive
            messages.error(request, "No preview data found. Please upload a file first.")
            return redirect("results:student_csv_upload")

        # Re-run the import in commit mode
        content = preview_data["content"]
        year_class_id = preview_data["year_class_id"]
        roll_numbers = preview_data.get("roll_numbers", [])
        stream = io.StringIO(content)

        importer = StudentCSVImporter(
            stream,
            started_by=request.user,
            filename=preview_data["filename"],
        )

        try:
            summary = importer.commit()

            # Update all students from this import to have the correct year_class
            # We use roll numbers to identify the students from this import
            from apps.accounts.models import Student

            if roll_numbers:
                Student.objects.filter(roll_number__in=roll_numbers).update(
                    year_class_id=year_class_id
                )

            # Transition results to SUBMITTED status
            # (Note: Students don't have status workflow, but results do)
            messages.success(
                request,
                f"Successfully imported {summary.created} students "
                f"(updated {summary.updated}, skipped {summary.skipped}).",
            )
        except ValueError as e:  # pragma: no cover - error handling
            messages.error(request, str(e))
            return redirect("results:student_csv_upload")
        finally:
            # Clear session data
            if "import_preview" in request.session:
                del request.session["import_preview"]

        # Redirect to admin if available, otherwise home
        if request.user.is_staff and request.user.has_perm("accounts.view_student"):
            return redirect("admin:accounts_student_changelist")
        return redirect("results:home")  # pragma: no cover - fallback


class ResultCSVUploadView(StaffRequiredMixin, FormView):
    """Upload result CSV and show dry-run preview."""

    template_name = "results/import/upload_results.html"
    form_class = ResultCSVUploadForm

    def form_valid(self, form):
        """Process the uploaded CSV in dry-run mode."""
        csv_file = form.cleaned_data["csv_file"]
        exam = form.cleaned_data["exam"]

        # Read and decode the file
        content = csv_file.read().decode("utf-8")
        stream = io.StringIO(content)

        # Run the importer in preview mode
        importer = ResultCSVImporter(
            stream,
            started_by=self.request.user,
            filename=csv_file.name,
        )

        try:
            summary = importer.preview()
        except ValueError as e:  # pragma: no cover - error handling
            messages.error(self.request, str(e))
            return self.form_invalid(form)

        # Store preview data in session for next step
        self.request.session["import_preview"] = {
            "type": "results",
            "batch_id": summary.batch.id,
            "exam_id": exam.id,
            "filename": csv_file.name,
            "content": content,
        }

        return redirect("results:result_csv_preview")


class ResultCSVPreviewView(StaffRequiredMixin, TemplateView):
    """Preview result CSV import results and allow submission."""

    template_name = "results/import/preview_results.html"

    def get(self, request, *args, **kwargs):
        """Show preview of import results."""
        preview_data = request.session.get("import_preview")
        if not preview_data or preview_data["type"] != "results":
            messages.error(request, "No preview data found. Please upload a file first.")
            return redirect("results:result_csv_upload")

        batch = ImportBatch.objects.get(id=preview_data["batch_id"])
        exam = Exam.objects.get(id=preview_data["exam_id"])

        context = self.get_context_data(**kwargs)
        context["batch"] = batch
        context["exam"] = exam
        context["errors"] = batch.errors_json
        context["warnings"] = batch.warnings_json

        return render(request, self.template_name, context)

    def post(self, request, *args, **kwargs):
        """Submit the import for real and transition to SUBMITTED."""
        preview_data = request.session.get("import_preview")
        if not preview_data or preview_data["type"] != "results":  # pragma: no cover - defensive
            messages.error(request, "No preview data found. Please upload a file first.")
            return redirect("results:result_csv_upload")

        # Re-run the import in commit mode
        content = preview_data["content"]
        exam_id = preview_data["exam_id"]
        stream = io.StringIO(content)

        importer = ResultCSVImporter(
            stream,
            started_by=request.user,
            filename=preview_data["filename"],
        )

        try:
            summary = importer.commit()

            # Link batch to exam
            batch = summary.batch
            batch.exam_id = exam_id
            batch.save(update_fields=["exam"])

            # Transition all created/updated results to SUBMITTED status and link to exam
            Result.objects.filter(import_batch=batch).update(
                status=Result.ResultStatus.SUBMITTED, exam_id=exam_id
            )

            messages.success(
                request,
                f"Successfully imported {summary.created} results "
                f"(updated {summary.updated}, skipped {summary.skipped}). "
                f"Results are now in SUBMITTED status awaiting verification.",
            )
        except ValueError as e:  # pragma: no cover - error handling
            messages.error(request, str(e))
            return redirect("results:result_csv_upload")
        finally:
            # Clear session data
            if "import_preview" in request.session:
                del request.session["import_preview"]

        # Redirect to admin if available, otherwise home
        if request.user.is_staff and request.user.has_perm("results.view_result"):
            return redirect("admin:results_result_changelist")
        return redirect("results:home")  # pragma: no cover - fallback
