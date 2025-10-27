"""Forms for CSV import."""

from django import forms

from apps.accounts.models import YearClass

from .models import Exam


class StudentCSVUploadForm(forms.Form):
    """Form for uploading student CSV files."""

    year_class = forms.ModelChoiceField(
        queryset=YearClass.objects.all(),
        required=True,
        label="Year/Class",
        help_text="Select the year/class for these students",
    )
    csv_file = forms.FileField(
        required=True,
        label="CSV File",
        help_text="Upload a CSV file with student data",
        widget=forms.FileInput(attrs={"accept": ".csv"}),
    )


class ResultCSVUploadForm(forms.Form):
    """Form for uploading result CSV files."""

    exam = forms.ModelChoiceField(
        queryset=Exam.objects.all(),
        required=True,
        label="Exam",
        help_text="Select the exam for these results",
    )
    csv_file = forms.FileField(
        required=True,
        label="CSV File",
        help_text="Upload a CSV file with result data",
        widget=forms.FileInput(attrs={"accept": ".csv"}),
    )
