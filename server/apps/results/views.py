"""Views for the results app."""

import io

from django.contrib import messages
from django.contrib.auth.mixins import UserPassesTestMixin
from django.shortcuts import redirect
from django.views.generic import FormView, ListView, TemplateView

from apps.accounts.importers import StudentCSVImporter
from apps.accounts.models import Student

from .forms import ResultCSVUploadForm, StudentCSVUploadForm
from .importers import ResultCSVImporter
from .models import Result


class TokenOrLoginRequiredMixin:
    """Mixin to require either token-based or standard authentication."""

    def dispatch(self, request, *args, **kwargs):
        # Check if user is authenticated via standard login
        if request.user.is_authenticated and hasattr(request.user, "student_profile"):
            return super().dispatch(request, *args, **kwargs)

        # Check if user is authenticated via token
        if request.session.get("token_authenticated") and request.session.get("token_student_id"):
            return super().dispatch(request, *args, **kwargs)

        # Not authenticated either way - redirect to token login
        messages.error(request, "Please log in to access your results.")
        return redirect("accounts:token_authenticate")

    def get_student(self):
        """Get the student for the current request (from user or token)."""
        # Standard authentication
        if self.request.user.is_authenticated and hasattr(self.request.user, "student_profile"):
            return self.request.user.student_profile

        # Token authentication
        student_id = self.request.session.get("token_student_id")
        if student_id:
            try:
                return Student.objects.get(id=student_id)
            except Student.DoesNotExist:
                pass

        return None


class HomeView(TemplateView):
    """Home page view."""

    template_name = "results/home.html"

    def get(self, request, *args, **kwargs):
        # If user is authenticated and has a student profile, redirect to their profile
        if request.user.is_authenticated and hasattr(request.user, "student_profile"):
            return redirect("results:student_profile")
        # Check token-based authentication
        if request.session.get("token_authenticated") and request.session.get("token_student_id"):
            return redirect("results:student_profile")
        return super().get(request, *args, **kwargs)


class StudentProfileView(TokenOrLoginRequiredMixin, TemplateView):
    """Student profile page showing basic information."""

    template_name = "results/student_profile.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        student = self.get_student()
        if not student:
            return context

        context["student"] = student
        context["published_results_count"] = (
            Result.objects.published().filter(student=student).count()
        )
        # Include exam information with recheck availability


        exams_with_results = []
        for result in Result.objects.published().filter(student=student).select_related("exam"):
            if result.exam and result.exam not in [e["exam"] for e in exams_with_results]:
                exams_with_results.append(
                    {
                        "exam": result.exam,
                        "recheck_open": result.exam.is_recheck_open() if result.exam else False,
                    }
                )
        context["exams_with_results"] = exams_with_results

        return context


class StudentResultsView(TokenOrLoginRequiredMixin, ListView):
    """Student results page showing only their own results."""

    template_name = "results/student_results.html"
    context_object_name = "results"
    paginate_by = 20

    def get_queryset(self):
        """Return only published results for the authenticated student."""
        student = self.get_student()
        if not student:
            return Result.objects.none()
        return Result.objects.published().filter(student=student).order_by("-exam_date", "subject")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        student = self.get_student()
        context["student"] = student
        return context


class StaffRequiredMixin(UserPassesTestMixin):
    """Mixin to require staff authentication."""

    def test_func(self):
        return self.request.user.is_authenticated and self.request.user.is_staff


class StudentCSVUploadView(StaffRequiredMixin, FormView):
    """Upload students.csv with year selection."""

    form_class = StudentCSVUploadForm
    template_name = "results/import/upload_students.html"

    def form_valid(self, form):
        csv_file = form.cleaned_data["csv_file"]
        year_class = form.cleaned_data["year_class"]

        # Read CSV content
        csv_content = csv_file.read().decode("utf-8")
        csv_file_obj = io.StringIO(csv_content)

        # Run dry-run preview
        importer = StudentCSVImporter(
            csv_file_obj, started_by=self.request.user, filename=csv_file.name
        )
        summary = importer.preview()

        # Store in session for review
        self.request.session["student_import_preview"] = {
            "year_class_id": year_class.id,
            "csv_content": csv_content,
            "row_count": summary.row_count,
            "created": summary.created,
            "updated": summary.updated,
            "skipped": summary.skipped,
            "has_errors": summary.has_errors,
            "errors": [
                {"row": r.row_number, "errors": r.errors}
                for r in summary.row_results
                if r.has_errors
            ],
            "warnings": [
                {"row": r.row_number, "warnings": r.messages}
                for r in summary.row_results
                if r.messages
            ],
        }

        return redirect("results:import_preview_students")


class StudentCSVPreviewView(StaffRequiredMixin, TemplateView):
    """Show dry-run preview with errors/warnings."""

    template_name = "results/import/preview_students.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        preview_data = self.request.session.get("student_import_preview")
        if not preview_data:
            messages.error(self.request, "No import preview found. Please upload a file first.")
            return context

        context.update(preview_data)
        return context

    def post(self, request):
        preview_data = request.session.get("student_import_preview")
        if not preview_data:
            messages.error(request, "No import preview found. Please upload a file first.")
            return redirect("results:upload_students")

        # Check if user wants to submit
        if "submit" in request.POST:
            csv_content = preview_data["csv_content"]
            csv_file_obj = io.StringIO(csv_content)

            # Apply the import using commit()
            importer = StudentCSVImporter(
                csv_file_obj, started_by=request.user, filename="students.csv"
            )
            summary = importer.commit()

            # Clear session
            del request.session["student_import_preview"]

            messages.success(
                request,
                f"Successfully imported {summary.created} new and updated {summary.updated} existing students.",
            )
            return redirect("admin:results_importbatch_changelist")

        return redirect("results:upload_students")


class ResultCSVUploadView(StaffRequiredMixin, FormView):
    """Upload results.csv with Exam selection."""

    form_class = ResultCSVUploadForm
    template_name = "results/import/upload_results.html"

    def form_valid(self, form):
        csv_file = form.cleaned_data["csv_file"]
        exam = form.cleaned_data["exam"]

        # Read CSV content
        csv_content = csv_file.read().decode("utf-8")
        csv_file_obj = io.StringIO(csv_content)

        # Run dry-run preview
        importer = ResultCSVImporter(
            csv_file_obj, started_by=self.request.user, filename=csv_file.name
        )
        summary = importer.preview()

        # Store in session for review
        self.request.session["result_import_preview"] = {
            "exam_id": exam.id,
            "batch_id": summary.batch.id,
            "csv_content": csv_content,
            "filename": csv_file.name,
            "row_count": summary.row_count,
            "created": summary.created,
            "updated": summary.updated,
            "skipped": summary.skipped,
            "has_errors": summary.has_errors,
            "errors": [
                {"row": r.row_number, "errors": r.errors}
                for r in summary.row_results
                if r.has_errors
            ],
            "warnings": [
                {"row": r.row_number, "warnings": r.messages}
                for r in summary.row_results
                if r.messages
            ],
        }

        return redirect("results:import_preview_results")


class ResultCSVPreviewView(StaffRequiredMixin, TemplateView):
    """Show dry-run preview with exam linkage."""

    template_name = "results/import/preview_results.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        preview_data = self.request.session.get("result_import_preview")
        if not preview_data:
            messages.error(self.request, "No import preview found. Please upload a file first.")
            return context

        from .models import Exam

        exam = Exam.objects.get(id=preview_data["exam_id"])
        context["exam"] = exam
        context.update(preview_data)
        return context

    def post(self, request):
        preview_data = request.session.get("result_import_preview")
        if not preview_data:
            messages.error(request, "No import preview found. Please upload a file first.")
            return redirect("results:upload_results")

        # Check if user wants to submit
        if "submit" in request.POST:
            csv_content = preview_data["csv_content"]
            filename = preview_data["filename"]
            csv_file_obj = io.StringIO(csv_content)

            # Apply the import using commit()
            importer = ResultCSVImporter(csv_file_obj, started_by=request.user, filename=filename)
            summary = importer.commit()

            # Transition results to SUBMITTED status
            results = Result.objects.filter(
                import_batch=summary.batch, status=Result.ResultStatus.DRAFT
            )
            for result in results:
                result.submit(user=request.user)

            # Clear session
            del request.session["result_import_preview"]

            messages.success(
                request,
                f"Successfully imported {summary.created} new and updated {summary.updated} existing results. "
                f"Results have been submitted for review.",
            )
            return redirect("admin:results_importbatch_changelist")

        return redirect("results:upload_results")
