from django import forms
from django.core.exceptions import ValidationError
from .models import Company, Country, State, City

class CompanyForm(forms.ModelForm):
    # Company fields
    company_name = forms.CharField(
        max_length=255,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter company name'})
    )
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Enter company email'})
    )
    mobile_number = forms.CharField(
        max_length=20,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter mobile number'})
    )
    website = forms.URLField(
        required=False,
        widget=forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'Enter website URL'})
    )
    gst_number = forms.CharField(
        max_length=50,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter GST number'})
    )
    cin_number = forms.CharField(
        max_length=50,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter CIN number'})
    )
    date_of_incorporation = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'})
    )
    contact_person = forms.CharField(
        max_length=255,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter contact person name'})
    )
    about_company = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'Enter company description'})
    )
    
    # Billing fields
    billing_address = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Enter billing address'})
    )
    billing_zip_code = forms.CharField(
        max_length=20,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter ZIP code'})
    )
    billing_country = forms.ModelChoiceField(
        queryset=Country.objects.filter(is_active=True).order_by('name'),
        required=False,
        empty_label="Select Country",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    billing_state = forms.ModelChoiceField(
        queryset=State.objects.filter(is_active=True).order_by('name'),
        required=False,
        empty_label="Select State",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    billing_city = forms.ModelChoiceField(
        queryset=City.objects.filter(is_active=True).order_by('name'),
        required=False,
        empty_label="Select City",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    # Company status
    listed_company = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    is_active = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    
    # Password fields (for admin user)
    password = forms.CharField(
        required=False,
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter password (required for new company)'
        })
    )
    confirm_password = forms.CharField(
        required=False,
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Confirm password'
        })
    )

    class Meta:
        model = Company
        fields = [
            'company_name', 'email', 'mobile_number', 'website',
            'gst_number', 'cin_number', 'date_of_incorporation',
            'contact_person', 'about_company',
            'billing_address', 'billing_zip_code', 'billing_country',
            'billing_state', 'billing_city', 'listed_company', 'is_active'
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # If editing (instance exists), clear password fields
        if self.instance and self.instance.pk:
            self.fields['password'].required = False
            self.fields['password'].widget.attrs['placeholder'] = 'Leave blank to keep current password'
            self.fields['confirm_password'].widget.attrs['placeholder'] = 'Leave blank to keep current password'
            self.fields['password'].help_text = 'Leave blank to keep current password'
            self.fields['confirm_password'].help_text = 'Leave blank to keep current password'
        else:
            # For new company, password is required
            self.fields['password'].required = True
            self.fields['confirm_password'].required = True
            self.fields['password'].help_text = 'Password is required for company admin'
            self.fields['confirm_password'].help_text = 'Confirm the password'

        # Filter states and cities based on country/state
        if 'billing_country' in self.data:
            try:
                country_id = int(self.data.get('billing_country'))
                self.fields['billing_state'].queryset = State.objects.filter(
                    country_id=country_id,
                    is_active=True
                ).order_by('name')
            except (ValueError, TypeError):
                pass
        elif self.instance and self.instance.pk and self.instance.billing_country_id:
            self.fields['billing_state'].queryset = State.objects.filter(
                country_id=self.instance.billing_country_id,
                is_active=True
            ).order_by('name')
            
        if 'billing_state' in self.data:
            try:
                state_id = int(self.data.get('billing_state'))
                self.fields['billing_city'].queryset = City.objects.filter(
                    state_id=state_id,
                    is_active=True
                ).order_by('name')
            except (ValueError, TypeError):
                pass
        elif self.instance and self.instance.pk and self.instance.billing_state_id:
            self.fields['billing_city'].queryset = City.objects.filter(
                state_id=self.instance.billing_state_id,
                is_active=True
            ).order_by('name')

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get('password')
        confirm_password = cleaned_data.get('confirm_password')
        
        # For new company, password is required
        if not self.instance.pk:
            if not password:
                self.add_error('password', 'Password is required for company admin.')
            elif not confirm_password:
                self.add_error('confirm_password', 'Please confirm the password.')
            elif password != confirm_password:
                self.add_error('confirm_password', 'Passwords do not match.')
        else:
            # For existing company, only validate if password is provided
            if password and password != confirm_password:
                self.add_error('confirm_password', 'Passwords do not match.')
        
        return cleaned_data

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if email:
            # Check if email already exists (excluding current instance)
            if self.instance.pk:
                if Company.objects.exclude(pk=self.instance.pk).filter(email=email).exists():
                    raise ValidationError('A company with this email already exists.')
            else:
                if Company.objects.filter(email=email).exists():
                    raise ValidationError('A company with this email already exists.')
        return email

    def clean_company_name(self):
        company_name = self.cleaned_data.get('company_name')
        if company_name:
            if self.instance.pk:
                if Company.objects.exclude(pk=self.instance.pk).filter(company_name__iexact=company_name).exists():
                    raise ValidationError('A company with this name already exists.')
            else:
                if Company.objects.filter(company_name__iexact=company_name).exists():
                    raise ValidationError('A company with this name already exists.')
        return company_name