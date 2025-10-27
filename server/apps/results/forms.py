"""Forms for CSV import workflows."""

from django import forms

from apps.accounts.models import YearClass

from .models import Exam


class StudentCSVUploadForm(forms.Form):
    """Form for uploading student CSV files."""

    csv_file = forms.FileField(
        label="Student CSV File",
        help_text="Upload a CSV file with student data",
        widget=forms.FileInput(attrs={"accept": ".csv", "class": "form-control"}),
    )
    year_class = forms.ModelChoiceField(
        queryset=YearClass.objects.all(),
        label="Year/Class",
        help_text="Select the year/class for these students",
        widget=forms.Select(attrs={"class": "form-select"}),
    )


class ResultCSVUploadForm(forms.Form):
    """Form for uploading result CSV files."""

    csv_file = forms.FileField(
        label="Results CSV File",
        help_text="Upload a CSV file with result data",
        widget=forms.FileInput(attrs={"accept": ".csv", "class": "form-control"}),
    )
    exam = forms.ModelChoiceField(
        queryset=Exam.objects.all().select_related("year_class"),
        label="Exam",
        help_text="Select the exam for these results",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
