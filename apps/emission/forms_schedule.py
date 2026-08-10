from django import forms

from .models import (
    EmissionAssignmentSchedule,
    EmissionSource,
)


class EmissionAssignmentScheduleForm(forms.ModelForm):

    source_ids = forms.ModelMultipleChoiceField(
        queryset=EmissionSource.objects.filter(
            is_active=True,
        ).order_by(
            "activity__display_order",
            "display_order",
        ),
        required=True,
        widget=forms.CheckboxSelectMultiple,
    )

    class Meta:

        model = EmissionAssignmentSchedule

        fields = [
            "name",
            "company",
            "plant",
            "scope",
            "assigner",
            "assignee",
            "reviewer",
            "workflow_template",
            "schedule_type",
            "frequency",
            "selected_months",
            "selected_quarters",
            "selected_half_years",
            "start_date",
            "end_date",
            "priority",
            "notes",
        ]

        widgets = {

            "name": forms.TextInput(
                attrs={
                    "class": "workspace-input",
                    "placeholder": "Schedule Name",
                }
            ),

            "company": forms.Select(
                attrs={
                    "class": "workspace-select",
                }
            ),

            "plant": forms.Select(
                attrs={
                    "class": "workspace-select",
                }
            ),

            "scope": forms.Select(
                attrs={
                    "class": "workspace-select",
                }
            ),

            "assigner": forms.Select(
                attrs={
                    "class": "workspace-select",
                }
            ),

            "assignee": forms.Select(
                attrs={
                    "class": "workspace-select",
                }
            ),

            "reviewer": forms.Select(
                attrs={
                    "class": "workspace-select",
                }
            ),

            "workflow_template": forms.Select(
                attrs={
                    "class": "workspace-select",
                }
            ),

            "schedule_type": forms.Select(
                attrs={
                    "class": "workspace-select",
                    "id": "scheduleType",
                }
            ),

            "frequency": forms.Select(
                attrs={
                    "class": "workspace-select",
                    "id": "frequency",
                }
            ),

            "start_date": forms.DateInput(
                attrs={
                    "type": "date",
                    "class": "workspace-input",
                }
            ),

            "end_date": forms.DateInput(
                attrs={
                    "type": "date",
                    "class": "workspace-input",
                }
            ),

            "priority": forms.Select(
                attrs={
                    "class": "workspace-select",
                }
            ),

            "notes": forms.Textarea(
                attrs={
                    "class": "workspace-textarea",
                    "rows": 3,
                }
            ),
        }

    def clean(self):

        cleaned_data = super().clean()

        schedule_type = cleaned_data.get("schedule_type")
        frequency = cleaned_data.get("frequency")
        start_date = cleaned_data.get("start_date")
        end_date = cleaned_data.get("end_date")

        months = cleaned_data.get("selected_months") or []
        quarters = cleaned_data.get("selected_quarters") or []
        half_years = cleaned_data.get("selected_half_years") or []

        source_ids = cleaned_data.get("source_ids")

        # --------------------------------------------------
        # Validate Emission Sources
        # --------------------------------------------------

        if not source_ids:
            raise forms.ValidationError(
                "Please select at least one emission source."
            )

        # --------------------------------------------------
        # One Time Schedule
        # --------------------------------------------------

        if schedule_type == "ONE_TIME":

            cleaned_data["frequency"] = None
            cleaned_data["selected_months"] = []
            cleaned_data["selected_quarters"] = []
            cleaned_data["selected_half_years"] = []
            cleaned_data["end_date"] = None

        # --------------------------------------------------
        # Recurring Schedule
        # --------------------------------------------------

        elif schedule_type == "RECURRING":

            if not frequency:
                raise forms.ValidationError(
                    "Please select a frequency."
                )

            if not end_date:
                raise forms.ValidationError(
                    "Please select an End Date."
                )

            if end_date <= start_date:
                raise forms.ValidationError(
                    "End Date must be greater than Start Date."
                )

            if frequency == "MONTHLY" and not months:
                raise forms.ValidationError(
                    "Please select at least one month."
                )

            if frequency == "QUARTERLY" and not quarters:
                raise forms.ValidationError(
                    "Please select at least one quarter."
                )

            if frequency == "HALF_YEARLY" and not half_years:
                raise forms.ValidationError(
                    "Please select at least one half year."
                )

        return cleaned_data