from django import forms
from django.contrib.auth import get_user_model

from apps.organizations.models import FinancialYear, Plant

from .models import Assignment, BRSRQuestion


User = get_user_model()


class BRSRAssignmentForm(forms.Form):
    plant = forms.ModelChoiceField(
        queryset=Plant.objects.none(),
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    financial_year = forms.ChoiceField(
        choices=(),
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    assigner = forms.ModelChoiceField(
        queryset=User.objects.none(),
        required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    assignee = forms.ModelChoiceField(
        queryset=User.objects.none(),
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    data_collection_frequency = forms.ChoiceField(
        choices=Assignment.FREQUENCY_CHOICES,
        required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    due_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={"type": "date", "class": "form-control"}),
    )
    priority = forms.ChoiceField(
        choices=Assignment.PRIORITY_CHOICES,
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    question_ids = forms.ModelMultipleChoiceField(
        queryset=BRSRQuestion.objects.none(),
        to_field_name='question_id',
        widget=forms.CheckboxSelectMultiple,
    )
    notes = forms.CharField(
        required=False,
        widget=forms.Textarea(
            attrs={"class": "form-control", "rows": 3, "placeholder": "Assignment notes"}
        ),
    )

    def __init__(self, *args, **kwargs):
        plant_queryset = kwargs.pop("plant_queryset", None)
        user_queryset = kwargs.pop("user_queryset", None)
        question_queryset = kwargs.pop("question_queryset", None)
        parent_queryset = kwargs.pop("parent_queryset", None)
        financial_year_queryset = kwargs.pop("financial_year_queryset", None)
        super().__init__(*args, **kwargs)

        self.fields["plant"].queryset = plant_queryset or Plant.objects.filter(is_active=True)
        self.fields["assigner"].queryset = user_queryset or User.objects.filter(is_active=True)
        self.fields["assignee"].queryset = user_queryset or User.objects.filter(is_active=True)
        # parent_assignment removed from the form — parent assignment delegation
        # is not used in the current workflow.
        self.fields["question_ids"].queryset = question_queryset or BRSRQuestion.objects.none()

        financial_year_qs = financial_year_queryset or FinancialYear.objects.all()
        financial_year_choices = [
            (fy.financial_year, fy.financial_year) for fy in financial_year_qs
        ]
        if not financial_year_choices:
            financial_year_choices = [("2024-2025", "2024-2025")]
        self.fields["financial_year"].choices = financial_year_choices

        if not self.is_bound and financial_year_choices:
            self.initial.setdefault("financial_year", financial_year_choices[0][0])
