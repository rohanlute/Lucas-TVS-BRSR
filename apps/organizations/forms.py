from django import forms
from django.forms import BaseInlineFormSet, inlineformset_factory
from django.core.exceptions import ValidationError
from .models import *
from apps.companies.models import Country, State, City
from apps.accounts.models import Role


class PlantForm(forms.ModelForm):
    """Plant Form"""
    
    class Meta:
        model = Plant
        fields = ['name', 'code', 'address','country', 'state', 'city', 'pincode', 
                  'contact_person', 'contact_email', 'contact_phone', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Plant Name'}),
            'code': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Plant Code (e.g., EP001)'}),
            'address': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Complete Address'}),
            'country': forms.Select(attrs={'class': 'form-control'}),
            'state': forms.Select(attrs={'class': 'form-control'}),
            'city': forms.Select(attrs={'class': 'form-control'}),
            'pincode': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Pincode'}),
            'contact_person': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Contact Person Name'}),
            'contact_email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Contact Email'}),
            'contact_phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Contact Phone'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields['country'].queryset = Country.objects.filter(is_active=True)

        self.fields['state'].queryset = State.objects.none()
        self.fields['city'].queryset = City.objects.none()

        # Edit page
        if self.instance.pk:

            if self.instance.country:
                self.fields['state'].queryset = State.objects.filter(
                    country=self.instance.country,
                    is_active=True
                )

            if self.instance.state:
                self.fields['city'].queryset = City.objects.filter(
                    state=self.instance.state,
                    is_active=True
                )

        # Create page
        if 'country' in self.data:
            try:
                country_id = int(self.data.get('country'))
                self.fields['state'].queryset = State.objects.filter(
                    country_id=country_id,
                    is_active=True
                )
            except (ValueError, TypeError):
                pass

        if 'state' in self.data:
            try:
                state_id = int(self.data.get('state'))
                self.fields['city'].queryset = City.objects.filter(
                    state_id=state_id,
                    is_active=True
                )
            except (ValueError, TypeError):
                pass
    
class FinancialYearForm(forms.ModelForm):
    class Meta:
        model = FinancialYear
        fields = ["financial_year", "start_date", "end_date"]
        widgets = {
            "financial_year": forms.TextInput(attrs={
                "class": "form-control"
            }),
            "start_date": forms.DateInput(attrs={
                "class": "form-control",
                "type": "date",
            }),
            "end_date": forms.DateInput(attrs={
                "class": "form-control",
                "type": "date",
            }),
        }
    def clean_financial_year(self):
        financial_year = self.cleaned_data["financial_year"].strip()

        try:
            start_year, end_year = map(int, financial_year.split("-"))
        except ValueError:
            raise ValidationError(
                "Financial year must be in the format YYYY-YYYY (e.g. 2022-2023)."
            )

        if end_year != start_year + 1:
            raise ValidationError(
                "Financial year must span consecutive years."
            )

        return financial_year

    def clean(self):
        cleaned_data = super().clean()

        financial_year = cleaned_data.get("financial_year")
        start_date = cleaned_data.get("start_date")
        end_date = cleaned_data.get("end_date")

        if start_date and end_date:
            if start_date >= end_date:
                self.add_error(
                    "end_date",
                    "End date must be later than start date."
                )

        if financial_year and start_date and end_date:
            start_year, end_year = map(int, financial_year.split("-"))

            if start_date.year != start_year:
                self.add_error(
                    "start_date",
                    "Start date does not match the financial year."
                )

            if end_date.year != end_year:
                self.add_error(
                    "end_date",
                    "End date does not match the financial year."
                )

        return cleaned_data      


class WorkflowConfigurationTemplateForm(forms.ModelForm):
    class Meta:
        model = ApprovalConfigurationTemplate
        fields = ["company", "framework", "name", "is_active"]
        widgets = {
            "company": forms.Select(attrs={"class": "form-select"}),
            "framework": forms.Select(attrs={"class": "form-select"}),
            "name": forms.TextInput(attrs={"class": "form-control", "placeholder": "e.g. BRSR Approval"}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }


class WorkflowConfigurationStageForm(forms.ModelForm):
    class Meta:
        model = ApprovalConfigurationStage
        fields = [
            "level",
            "label",
            "stage_type",
            "role",
            "can_approve",
            "can_reject",
            "can_reassign",
            "can_escalate",
            "due_days",
            "escalation_role",
        ]
        widgets = {
            "level": forms.HiddenInput(),
            "label": forms.TextInput(attrs={"class": "form-control", "placeholder": "Stage label"}),
            "stage_type": forms.Select(attrs={"class": "form-select"}),
            "role": forms.Select(attrs={"class": "form-select"}),
            "can_approve": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "can_reject": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "can_reassign": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "can_escalate": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "due_days": forms.NumberInput(attrs={"class": "form-control", "min": 1, "placeholder": "Days"}),
            "escalation_role": forms.Select(attrs={"class": "form-select"}),
        }

    def clean(self):
        cleaned_data = super().clean()
        stage_type = cleaned_data.get("stage_type")
        if stage_type in ["question_assignment","data_entry","review",]:
            cleaned_data["due_days"] = None
        
        return cleaned_data
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        role_qs = Role.objects.filter(is_active=True).order_by("role_name")
        self.fields["role"].queryset = role_qs
        self.fields["escalation_role"].queryset = role_qs
        self.fields["escalation_role"].required = False


class BaseWorkflowConfigurationStageFormSet(BaseInlineFormSet):
    def clean(self):
        super().clean()

        non_deleted_forms = []

        for form in self.forms:
            if not hasattr(form, "cleaned_data"):
                continue

            if form.cleaned_data.get("DELETE"):
                continue

            # Skip completely empty extra forms, but keep unchanged existing stages.
            if not form.instance.pk and not form.has_changed():
                continue

            non_deleted_forms.append(form)

        if not non_deleted_forms:
            raise ValidationError("At least one approval stage is required.")

        stage_types = [
            form.cleaned_data.get("stage_type")
            for form in non_deleted_forms
        ]

        if "final_approval" in stage_types:
            if stage_types[-1] != "final_approval":
                raise ValidationError("Final Approval stage must be the last stage.")

            if stage_types.count("final_approval") > 1:
                raise ValidationError("Only one Final Approval stage is allowed.")

        for form in non_deleted_forms:
            role = form.cleaned_data.get("role")
            label = (form.cleaned_data.get("label") or "").strip()

            if not label:
                raise ValidationError("Each stage requires a label.")

            if role is None:
                raise ValidationError("Each stage requires a role.")
            
WorkflowConfigurationStageFormSet = inlineformset_factory(
    ApprovalConfigurationTemplate,
    ApprovalConfigurationStage,
    form=WorkflowConfigurationStageForm,
    formset=BaseWorkflowConfigurationStageFormSet,
    extra=1,
    can_delete=True,
)


# Backward-compatible aliases for any remaining imports.
ApprovalConfigurationTemplateForm = WorkflowConfigurationTemplateForm
ApprovalConfigurationStageForm = WorkflowConfigurationStageForm
BaseApprovalConfigurationStageFormSet = BaseWorkflowConfigurationStageFormSet
ApprovalConfigurationStageFormSet = WorkflowConfigurationStageFormSet
