"""Presentation layer for authentication workflows."""

from django.conf import settings
from django.contrib import messages
from django.shortcuts import redirect
from django.urls import reverse
from django.views.generic import FormView, TemplateView

from .forms import TokenAuthenticateForm, TokenRequestForm
from .models import StudentAccessToken


class GoogleLoginView(TemplateView):
    """Render a simple Google Workspace sign-in page."""

    template_name = "accounts/login.html"

    def dispatch(self, request, *args, **kwargs):  # pragma: no cover - simple guard
        if request.user.is_authenticated:
            messages.info(request, "You are already signed in.")
            return redirect("/")
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "google_login_url": reverse("social:begin", args=["google-oauth2"]),
                "workspace_domain": settings.GOOGLE_WORKSPACE_DOMAIN,
            }
        )
        return context


class TokenRequestView(FormView):
    """View for students to request an access token."""

    template_name = "accounts/token_login.html"
    form_class = TokenRequestForm

    def form_valid(self, form):
        student = form.cleaned_data["student"]

        # Generate access token (24 hour validity)
        token = StudentAccessToken.generate_for_student(student, validity_hours=24)

        # Store token in session to display it once
        self.request.session["token_code"] = token.code
        self.request.session["token_expires"] = token.expires_at.isoformat()
        self.request.session["token_student_id"] = student.id

        messages.success(self.request, "Access token generated successfully!")
        return redirect("accounts:token_success")


class TokenSuccessView(TemplateView):
    """View to display the generated token (shown only once)."""

    template_name = "accounts/token_success.html"

    def dispatch(self, request, *args, **kwargs):
        # Ensure token info exists in session
        if "token_code" not in request.session:
            messages.error(request, "No token found. Please request a new token.")
            return redirect("accounts:token_request")
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Retrieve token from session


        token_code = self.request.session.get("token_code")
        token_expires_str = self.request.session.get("token_expires")
        import datetime as dt

        token_expires = dt.datetime.fromisoformat(token_expires_str)

        context["token"] = {
            "code": token_code,
            "expires_at": token_expires,
        }

        # Clear token from session after displaying
        del self.request.session["token_code"]
        del self.request.session["token_expires"]

        return context


class TokenAuthenticateView(FormView):
    """View for students to authenticate using their access token."""

    template_name = "accounts/token_authenticate.html"
    form_class = TokenAuthenticateForm

    def form_valid(self, form):
        token = form.cleaned_data["token"]

        # Mark token as used
        token.mark_used()

        # Store student ID in session for token-based authentication
        self.request.session["token_student_id"] = token.student.id
        self.request.session["token_authenticated"] = True

        messages.success(
            self.request,
            f"Welcome, {token.student.display_name or token.student.roll_number}!",
        )
        return redirect("results:student_profile")
