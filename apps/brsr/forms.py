from django import forms
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from apps.organizations.models import FinancialYear, Plant
from .models import Assignment, BRSRQuestion, AssignmentSchedule, AssignmentReviewer


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
    # For GenericForeignKey, we need to use content_type and object_id
    assigner_content_type = forms.ModelChoiceField(
        queryset=ContentType.objects.all(),
        required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
        label="Assigner Type"
    )
    assigner_object_id = forms.IntegerField(
        required=False,
        widget=forms.NumberInput(attrs={"class": "form-control"}),
        label="Assigner ID"
    )
    assignee_content_type = forms.ModelChoiceField(
        queryset=ContentType.objects.all(),
        required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
        label="Assignee Type"
    )
    assignee_object_id = forms.IntegerField(
        required=False,
        widget=forms.NumberInput(attrs={"class": "form-control"}),
        label="Assignee ID"
    )
    reviewer_content_type = forms.ModelChoiceField(
        queryset=ContentType.objects.all(),
        required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
        label="Reviewer Type"
    )
    reviewer_object_id = forms.IntegerField(
        required=False,
        widget=forms.NumberInput(attrs={"class": "form-control"}),
        label="Reviewer ID"
    )
    data_collection_frequency = forms.ChoiceField(
        choices=Assignment.FREQUENCY_CHOICES,
        required=True,
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
    weekly_start_day = forms.TypedChoiceField(
        choices=AssignmentSchedule.WEEKDAY_CHOICES, coerce=int, required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    weekly_end_day = forms.TypedChoiceField(
        choices=AssignmentSchedule.WEEKDAY_CHOICES, coerce=int, required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    selected_months = forms.MultipleChoiceField(
        choices=AssignmentSchedule.MONTH_CHOICES, required=False,
        widget=forms.CheckboxSelectMultiple,
    )
    selected_quarters = forms.MultipleChoiceField(
        choices=AssignmentSchedule.QUARTER_CHOICES, required=False,
        widget=forms.CheckboxSelectMultiple,
    )
    schedule_name = forms.CharField(
        required=False, max_length=150,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "e.g. Monthly Energy Data Collection"}),
    )

    def clean(self):
        cleaned = super().clean()
        frequency = cleaned.get("data_collection_frequency")
        if not frequency:
            return cleaned

        if frequency == "weekly":
            start_day = cleaned.get("weekly_start_day")
            end_day = cleaned.get("weekly_end_day")
            if start_day is None or end_day is None:
                self.add_error(None, "Weekly frequency requires both a Start Day and an End Day.")
            elif start_day > end_day:
                self.add_error(None, "Start Day must come before End Day (e.g. Monday → Friday).")
        elif frequency == "monthly":
            months = cleaned.get("selected_months") or []
            if not months:
                self.add_error(None, "Select at least one month for monthly frequency.")
            else:
                cleaned["selected_months"] = [int(m) for m in months]
        elif frequency == "quarterly":
            quarters = cleaned.get("selected_quarters") or []
            if not quarters:
                self.add_error(None, "Select at least one quarter for quarterly frequency.")

        return cleaned

    def __init__(self, *args, **kwargs):
        plant_queryset = kwargs.pop("plant_queryset", None)
        user_queryset = kwargs.pop("user_queryset", None)
        question_queryset = kwargs.pop("question_queryset", None)
        parent_queryset = kwargs.pop("parent_queryset", None)
        financial_year_queryset = kwargs.pop("financial_year_queryset", None)
        super().__init__(*args, **kwargs)

        self.fields["plant"].queryset = plant_queryset or Plant.objects.filter(is_active=True)
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


class AssignmentScheduleForm(forms.ModelForm):
    """
    Admin-facing form for creating a reusable AssignmentSchedule. This is
    the "template" — it never creates an Assignment itself; the Celery Beat
    task does that when a configured period becomes due.
    """
 
    # For GenericForeignKey, use content_type and object_id
    assignee_content_type = forms.ModelChoiceField(
        queryset=ContentType.objects.all(),
        required=False,
        widget=forms.Select(attrs={"class": "workspace-select"}),
        label="Assignee Type"
    )
    assignee_object_id = forms.IntegerField(
        required=False,
        widget=forms.NumberInput(attrs={"class": "workspace-input"}),
        label="Assignee ID"
    )
    reviewer_content_type = forms.ModelChoiceField(
        queryset=ContentType.objects.all(),
        required=False,
        widget=forms.Select(attrs={"class": "workspace-select"}),
        label="Reviewer Type"
    )
    reviewer_object_id = forms.IntegerField(
        required=False,
        widget=forms.NumberInput(attrs={"class": "workspace-input"}),
        label="Reviewer ID"
    )
    due_period_days = forms.IntegerField(
        required=False,
        min_value=1,
        widget=forms.NumberInput(attrs={"class": "workspace-input", "placeholder": "e.g. 15"}),
        label="Due Period (days)"
    )
    question_ids = forms.ModelMultipleChoiceField(
        queryset=BRSRQuestion.objects.none(),
        to_field_name='question_id',
        widget=forms.CheckboxSelectMultiple,
    )
    selected_months = forms.MultipleChoiceField(
        choices=AssignmentSchedule.MONTH_CHOICES,
        required=False,
        widget=forms.CheckboxSelectMultiple,
    )
    selected_quarters = forms.MultipleChoiceField(
        choices=AssignmentSchedule.QUARTER_CHOICES,
        required=False,
        widget=forms.CheckboxSelectMultiple,
    )
 
    class Meta:
        model = AssignmentSchedule
        fields = [
            "name", "plant", "financial_year", "frequency",
            "weekly_start_day", "weekly_end_day", "priority", "due_period_days", "notes",
        ]
        widgets = {
            "name": forms.TextInput(attrs={"class": "workspace-input", "placeholder": "e.g. Monthly Energy Data Collection"}),
            "plant": forms.Select(attrs={"class": "workspace-select"}),
            "frequency": forms.Select(attrs={"class": "workspace-select", "id": "scheduleFrequency"}),
            "weekly_start_day": forms.Select(attrs={"class": "workspace-select"}),
            "weekly_end_day": forms.Select(attrs={"class": "workspace-select"}),
            "priority": forms.Select(attrs={"class": "workspace-select"}),
            "notes": forms.Textarea(attrs={"class": "workspace-textarea", "rows": 3}),
        }
 
    def __init__(self, *args, **kwargs):
        plant_queryset = kwargs.pop("plant_queryset", None)
        user_queryset = kwargs.pop("user_queryset", None)
        question_queryset = kwargs.pop("question_queryset", None)
        financial_year_queryset = kwargs.pop("financial_year_queryset", None)
        super().__init__(*args, **kwargs)
 
        self.fields["plant"].queryset = plant_queryset or Plant.objects.filter(is_active=True)
        self.fields["question_ids"].queryset = question_queryset or BRSRQuestion.objects.none()
 
        financial_year_qs = financial_year_queryset or FinancialYear.objects.all()
        fy_choices = [(fy.financial_year, fy.financial_year) for fy in financial_year_qs]
        if not fy_choices:
            fy_choices = [("2024-2025", "2024-2025")]
        self.fields["financial_year"] = forms.ChoiceField(
            choices=fy_choices, widget=forms.Select(attrs={"class": "workspace-select"})
        )
        if not self.is_bound:
            self.initial.setdefault("financial_year", fy_choices[0][0])
 
    def clean(self):
        cleaned = super().clean()
        frequency = cleaned.get("frequency")
 
        if frequency == "weekly":
            start_day = cleaned.get("weekly_start_day")
            end_day = cleaned.get("weekly_end_day")
            if start_day is None or end_day is None:
                self.add_error(None, "Weekly frequency requires both a Start Day and an End Day.")
            elif start_day > end_day:
                self.add_error(None, "Start Day must come before End Day (e.g. Monday → Friday).")
 
        elif frequency == "monthly":
            months = cleaned.get("selected_months") or []
            if not months:
                self.add_error(None, "Select at least one month for monthly frequency.")
            else:
                cleaned["selected_months"] = [int(m) for m in months]
 
        elif frequency == "quarterly":
            quarters = cleaned.get("selected_quarters") or []
            if not quarters:
                self.add_error(None, "Select at least one quarter for quarterly frequency.")
 
        return cleaned