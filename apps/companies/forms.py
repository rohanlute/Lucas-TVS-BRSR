from django import forms
from django.core.exceptions import ValidationError
from .models import Company, Country, State, City

class CompanyForm(forms.ModelForm):
    # Company fields
    company_name = forms.CharField(
        max_length=255,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter company name',
            'autocomplete': 'off',
        })
    )
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter company email',
            'autocomplete': 'off',
        })
    )
    mobile_number = forms.CharField(
        max_length=20,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter mobile number',
            'autocomplete': 'off',
        })
    )
    website = forms.URLField(
        required=False,
        widget=forms.URLInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter website URL',
            'autocomplete': 'off',
        })
    )
    
    # Company Logo Field (styling matches Profile Picture upload in the template)
    company_logo = forms.ImageField(
        required=False,
        widget=forms.FileInput(attrs={
            'class': 'file-upload form-control-file position-absolute top-0 start-0 w-100 h-100',
            'accept': 'image/*',
            'autocomplete': 'off',
        })
    )
    
    # ✅ autocomplete='off' stops the browser from suggesting/filling a
    # saved "username" value into this field just because it sits above
    # a password field later in the same <form>.
    gst_number = forms.CharField(
        max_length=50,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter GST number',
            'autocomplete': 'off',
        })
    )
    cin_number = forms.CharField(
        max_length=50,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter CIN number',
            'autocomplete': 'off',
        })
    )
    date_of_incorporation = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date',
            'autocomplete': 'off',
        })
    )
    contact_person = forms.CharField(
        max_length=255,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter contact person name',
            'autocomplete': 'off',
        })
    )
    about_company = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 4,
            'placeholder': 'Enter company description',
            'autocomplete': 'off',
        })
    )
    
    # Billing fields
    billing_address = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Enter billing address',
            'autocomplete': 'off',
        })
    )
    billing_zip_code = forms.CharField(
        max_length=20,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter ZIP code',
            'autocomplete': 'off',
        })
    )
    billing_country = forms.ModelChoiceField(
        queryset=Country.objects.filter(is_active=True).order_by('name'),
        required=False,
        empty_label="Select Country",
        widget=forms.Select(attrs={'class': 'form-control', 'autocomplete': 'off'})
    )
    billing_state = forms.ModelChoiceField(
        queryset=State.objects.filter(is_active=True).order_by('name'),
        required=False,
        empty_label="Select State",
        widget=forms.Select(attrs={'class': 'form-control', 'autocomplete': 'off'})
    )
    billing_city = forms.ModelChoiceField(
        queryset=City.objects.filter(is_active=True).order_by('name'),
        required=False,
        empty_label="Select City",
        widget=forms.Select(attrs={'class': 'form-control', 'autocomplete': 'off'})
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
    
    # ✅ Password fields (for admin user)
    # autocomplete='new-password' is the one value browsers reliably respect
    # for password inputs (autocomplete='off' is widely ignored on <input
    # type="password">). This stops Chrome/Edge/Firefox from silently
    # filling in a previously saved login password on the Create page.
    password = forms.CharField(
        required=False,
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter new password (leave blank to keep current)',
            'autocomplete': 'new-password',
        })
    )
    confirm_password = forms.CharField(
        required=False,
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Confirm new password',
            'autocomplete': 'new-password',
        })
    )

    class Meta:
        model = Company
        fields = [
            'company_name', 'email', 'mobile_number', 'website',
            'company_logo',
            'gst_number', 'cin_number', 'date_of_incorporation',
            'contact_person', 'about_company',
            'billing_address', 'billing_zip_code', 'billing_country',
            'billing_state', 'billing_city', 'listed_company', 'is_active'
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # ✅ Explicitly force password fields empty on every render.
        # Combined with CompanyUpdateView.get_initial() (which already does
        # this for Edit), this guarantees Create always starts blank too -
        # nothing in Django itself was pre-filling these; this is just an
        # extra safety net alongside the autocomplete/decoy-field fixes.
        self.initial['password'] = ''
        self.initial['confirm_password'] = ''

        # If editing (instance exists), clear password fields
        if self.instance and self.instance.pk:
            self.fields['password'].required = False
            self.fields['password'].widget.attrs['placeholder'] = 'Leave blank to keep current password'
            self.fields['confirm_password'].required = False
            self.fields['confirm_password'].widget.attrs['placeholder'] = 'Leave blank to keep current password'
            self.fields['password'].help_text = 'Leave blank to keep current password'
            self.fields['confirm_password'].help_text = 'Leave blank to keep current password'
        else:
            # For new company, password is required
            self.fields['password'].required = True
            self.fields['confirm_password'].required = True
            self.fields['password'].widget.attrs['placeholder'] = 'Enter password (required)'
            self.fields['confirm_password'].widget.attrs['placeholder'] = 'Confirm password'
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

    def clean_company_logo(self):
        logo = self.cleaned_data.get('company_logo')
        if logo:
            # Validate file size (max 5MB)
            if logo.size > 5 * 1024 * 1024:
                raise ValidationError('Logo file size must be under 5MB.')
            
            # Validate file type
            valid_types = ['image/jpeg', 'image/png', 'image/gif', 'image/webp']
            if logo.content_type not in valid_types:
                raise ValidationError('Logo must be JPEG, PNG, GIF, or WebP format.')
        
        return logo

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
    def clean_company_logo(self):
        logo = self.cleaned_data.get('company_logo')
        if logo:
            # Check if it's a new file upload or existing file
            if hasattr(logo, 'file'):  # It's a new upload
                # Validate file size (max 5MB)
                if logo.size > 5 * 1024 * 1024:
                    raise ValidationError('Logo file size must be under 5MB.')
                
                # Validate file type - access content_type from the file object
                try:
                    # For uploaded files, content_type is on the file object
                    content_type = logo.file.content_type if hasattr(logo.file, 'content_type') else None
                    
                    # If content_type is not available, check the file extension
                    if not content_type:
                        import mimetypes
                        content_type = mimetypes.guess_type(logo.name)[0]
                    
                    valid_types = ['image/jpeg', 'image/png', 'image/gif', 'image/webp']
                    if content_type and content_type not in valid_types:
                        raise ValidationError('Logo must be JPEG, PNG, GIF, or WebP format.')
                except Exception:
                    # If we can't determine content type, just check extension
                    valid_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.webp']
                    if not any(logo.name.lower().endswith(ext) for ext in valid_extensions):
                        raise ValidationError('Logo must be JPEG, PNG, GIF, or WebP format.')
        
        return logo