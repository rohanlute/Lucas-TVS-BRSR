from django import forms

from .models import EmissionAssignment, EmissionTransaction


class EmissionTransactionForm(forms.ModelForm):

    class Meta:

        model = EmissionTransaction

        fields = (
            "company",
            "plant",
            "financial_year",
            "financial_month",
            "activity",
            "unit",
            "quantity",
            "remarks",
        )

        widgets = {

            "company": forms.Select(
                attrs={
                    "class": "form-select",
                }
            ),

            "plant": forms.Select(
                attrs={
                    "class": "form-select",
                }
            ),

            "financial_year": forms.Select(
                attrs={
                    "class": "form-select",
                }
            ),

            "financial_month": forms.Select(
                attrs={
                    "class": "form-select",
                }
            ),

            "activity": forms.Select(
                attrs={
                    "class": "form-select",
                }
            ),

            "unit": forms.Select(
                attrs={
                    "class": "form-select",
                }
            ),

            "quantity": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "step": "0.0001",
                    "placeholder": "Enter Quantity",
                }
            ),

            "remarks": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 3,
                    "placeholder": "Remarks",
                }
            ),
        }

    def __init__(self, *args, **kwargs):

        super().__init__(*args, **kwargs)

        self.fields["company"].empty_label = "Select Company"
        self.fields["plant"].empty_label = "Select Plant"
        self.fields["financial_year"].empty_label = "Select Financial Year"
        self.fields["financial_month"].empty_label = "Select Financial Month"
        self.fields["activity"].empty_label = "Select Activity"
        self.fields["unit"].empty_label = "Select Unit"

    def clean(self):

        cleaned_data = super().clean()

        company = cleaned_data.get("company")
        plant = cleaned_data.get("plant")
        financial_year = cleaned_data.get("financial_year")
        financial_month = cleaned_data.get("financial_month")
        activity = cleaned_data.get("activity")

        if company and plant and financial_year and financial_month and activity:

            exists = EmissionTransaction.objects.filter(
                company=company,
                plant=plant,
                financial_year=financial_year,
                financial_month=financial_month,
                activity=activity,
            )

            if self.instance.pk:
                exists = exists.exclude(pk=self.instance.pk)

            if exists.exists():

                raise forms.ValidationError(
                    "This emission transaction already exists."
                )

        return cleaned_data
    


class EmissionAssignmentForm(forms.ModelForm):

    class Meta:
        model = EmissionAssignment

        fields = [
            "company",
            "plant",
            "financial_year",
            "financial_month",
            "scope",
            "assignee",
            "due_date",
            "priority",
            "notes",
        ]