"""Forms for student token-based authentication."""

from django import forms
from django.core.exceptions import ValidationError

from .models import Student, StudentAccessToken


class TokenRequestForm(forms.Form):
    """Form for students to request an access token."""

    roll_number = forms.CharField(
        max_length=32,
        required=True,
        help_text="Your institutional roll number",
    )
    email = forms.EmailField(
        required=False,
        help_text="Your institutional email address",
    )
    phone = forms.CharField(
        max_length=20,
        required=False,
        help_text="Your registered phone number",
    )

    def clean(self):
        cleaned_data = super().clean()
        roll_number = cleaned_data.get("roll_number")
        email = cleaned_data.get("email")
        phone = cleaned_data.get("phone")

        # Require at least one contact method
        if not email and not phone:
            raise ValidationError("Please provide either your institutional email or phone number.")

        # Verify student exists and contact info matches
        try:
            student = Student.objects.get(roll_number=roll_number)
        except Student.DoesNotExist as e:
            raise ValidationError("Student with this roll number not found.") from e

        # Verify contact information
        if email and student.official_email.lower() != email.lower():
            raise ValidationError(
                "The email address does not match our records for this roll number."
            )

        if phone and student.phone != phone:
            raise ValidationError(
                "The phone number does not match our records for this roll number."
            )

        cleaned_data["student"] = student
        return cleaned_data


class TokenAuthenticateForm(forms.Form):
    """Form for students to authenticate with their access token."""

    token = forms.CharField(
        max_length=64,
        required=True,
        widget=forms.TextInput(attrs={"placeholder": "Enter your access token"}),
    )

    def clean_token(self):
        token_code = self.cleaned_data.get("token")

        try:
            token = StudentAccessToken.objects.get(code=token_code)
        except StudentAccessToken.DoesNotExist as e:
            raise ValidationError("Invalid access token.") from e

        if not token.is_valid():
            raise ValidationError("This access token has expired or has already been used.")

        return token
