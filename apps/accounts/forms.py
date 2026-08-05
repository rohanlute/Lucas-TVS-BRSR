from django import forms
from .models import User, Role, Department
from apps.accounts.models.permission import Permissions
from apps.companies.models import Company
import re

class UserCreateForm(forms.ModelForm):
    password = forms.CharField(
        required=False,
        widget=forms.PasswordInput(
            attrs={
                'class': 'form-control',
                'placeholder': 'Password (min 8 characters)',
                'id': 'passwordInput',
                'autocomplete': 'new-password',
                'autofill': 'off',
            }
        ),
    )

    confirm_password = forms.CharField(
        required=False,
        widget=forms.PasswordInput(
            attrs={
                'class': 'form-control password',
                'placeholder': 'Password Confirm',
                'id': 'confirmPasswordInput',
                'autocomplete': 'new-password',
                'autofill': 'off',
            }
        )
    )

    role = forms.ModelChoiceField(
        queryset=Role.objects.exclude(role_code='SUPERADMIN').order_by('role_name'),
        empty_label='Select Role',
        widget=forms.Select(
            attrs={
                'class': 'form-control',
            }
        ),
    )

    department = forms.ModelChoiceField(
        queryset=Department.objects.filter(
            is_active=True
        ).order_by('name'),
        required=False,
        empty_label='Select Department',
        widget=forms.Select(
            attrs={
                'class': 'form-control',
            }
        ),
    )

    company = forms.ModelChoiceField(
        queryset=Company.objects.filter(is_active=True).order_by('company_name'),
        empty_label='Select Company',
        widget=forms.Select(
            attrs={
                'class': 'form-control',
            }
        ),
    )

    class Meta:
        model = User
        fields = [
            'role',
            'company',
            'designation',
            'employee_code',
            'full_name',
            'email',
            'username',
            'mobile_number',
            'department',
            'profile_image',
            'is_active',
        ]
        widgets = {
            'full_name': forms.TextInput(
                attrs={
                    'class': 'form-control',
                    'placeholder': 'Name',
                    'id': 'fullnameInput',
                    'autocomplete': 'off',
                }
            ),
            'email': forms.EmailInput(
                attrs={
                    'class': 'form-control',
                    'placeholder': 'Email',
                    'id': 'mailInput',
                    'autocomplete': 'off',
                }
            ),
            'username': forms.TextInput(
                attrs={
                    'class': 'form-control',
                    'placeholder': 'Username',
                    'id': 'usernameInput',
                    'autocomplete': 'off',
                }
            ),
            'mobile_number': forms.NumberInput(
                attrs={
                    'class': 'form-control',
                    'placeholder': 'Phone',
                    'id': 'phoneInput',
                    'autocomplete': 'off',
                }
            ),
            'designation': forms.TextInput(
                attrs={
                    'class': 'form-control',
                    'placeholder': 'Designation',
                    'autocomplete': 'off',
                }
            ),
            'employee_code': forms.TextInput(
                attrs={
                    'class': 'form-control',
                    'placeholder': 'Employee ID',
                    'id': 'employee_codeInput',
                    'autocomplete': 'off',
                }
            ),
            'is_active': forms.CheckboxInput(
                attrs={
                    'class': 'form-check-input',
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Exclude SUPERADMIN from role choices
        self.fields['role'].queryset = Role.objects.exclude(role_code='SUPERADMIN').order_by('role_name')
        
        # Check if this is an update (instance exists)
        if self.instance and self.instance.pk:
            # For updates, password is optional
            self.fields['password'].required = False
            self.fields['confirm_password'].required = False
            self.fields['password'].help_text = "Leave blank to keep current password"
            self.fields['confirm_password'].help_text = "Leave blank to keep current password"
            
            # For updates, populate fields with instance data
            self.fields['username'].initial = self.instance.username
            self.fields['full_name'].initial = self.instance.full_name
            self.fields['email'].initial = self.instance.email
            self.fields['mobile_number'].initial = self.instance.mobile_number
            self.fields['designation'].initial = self.instance.designation
            self.fields['employee_code'].initial = self.instance.employee_code
            self.fields['is_active'].initial = self.instance.is_active
            
        else:
            # For new users, password is required
            self.fields['password'].required = True
            self.fields['confirm_password'].required = True
            self.fields['password'].help_text = "Password must contain uppercase, lowercase, numbers, and be at least 8 characters"
            self.fields['confirm_password'].help_text = "Please confirm the password"
            
            # For new users: Set ALL fields to empty string
            self.fields['username'].initial = ''
            self.fields['password'].initial = ''
            self.fields['confirm_password'].initial = ''
            self.fields['full_name'].initial = ''
            self.fields['email'].initial = ''
            self.fields['mobile_number'].initial = ''
            self.fields['designation'].initial = ''
            self.fields['employee_code'].initial = ''
            
            # Set default values
            self.fields['is_active'].initial = True
            
            # Override the widget to force empty value
            self.fields['username'].widget.attrs['value'] = ''
            self.fields['password'].widget.attrs['value'] = ''
            self.fields['confirm_password'].widget.attrs['value'] = ''
            self.fields['full_name'].widget.attrs['value'] = ''
            self.fields['email'].widget.attrs['value'] = ''
            self.fields['mobile_number'].widget.attrs['value'] = ''
            self.fields['designation'].widget.attrs['value'] = ''
            self.fields['employee_code'].widget.attrs['value'] = ''

    def validate_password_strength(self, password):
        """
        Comprehensive password validation with detailed error messages
        """
        errors = []
        
        # Check minimum length
        if len(password) < 8:
            errors.append("Password must be at least 8 characters long.")
        
        # Check for uppercase letter
        if not any(char.isupper() for char in password):
            errors.append("Password must contain at least one uppercase letter (A-Z).")
        
        # Check for lowercase letter
        if not any(char.islower() for char in password):
            errors.append("Password must contain at least one lowercase letter (a-z).")
        
        # Check for digit
        if not any(char.isdigit() for char in password):
            errors.append("Password must contain at least one number (0-9).")
        
        # Check for special character
        special_chars = r'[!@#$%^&*(),.?":{}|<>]'
        if not re.search(special_chars, password):
            errors.append("Password must contain at least one special character (!@#$%^&*(),.?\":{}|<>).")
        
        # Check for common weak passwords
        common_passwords = [
            'password', 'password123', '12345678', 'qwerty', 'abc123',
            'admin123', 'welcome', 'letmein', 'iloveyou', 'sunshine',
            '123456789', 'password1', '1234567890', 'admin', 'qwerty123',
            'welcome123', 'monkey', 'dragon', 'master', 'hello'
        ]
        if password.lower() in common_passwords:
            errors.append("This password is too common. Please choose a stronger password.")
        
        # Check if password contains username or email parts (if available)
        username = self.cleaned_data.get('username', '')
        if username and username.lower() in password.lower():
            errors.append("Password cannot contain your username.")
        
        email = self.cleaned_data.get('email', '')
        if email:
            email_parts = email.split('@')[0]
            if email_parts and email_parts.lower() in password.lower():
                errors.append("Password cannot contain your email username.")
        
        return errors

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get('password')
        confirm_password = cleaned_data.get('confirm_password')
        
        # Check if this is a new user or existing
        is_editing = self.instance and self.instance.pk
        
        # For new users, password is required
        if not is_editing and not password:
            self.add_error('password', "Password is required for new users.")
            return cleaned_data
        
        # For editing, skip validation if both are empty
        if is_editing and not password and not confirm_password:
            return cleaned_data
        
        # Only validate if password is provided
        if password:
            # Validate password strength
            password_errors = self.validate_password_strength(password)
            
            for error in password_errors:
                self.add_error('password', error)
            
            # Check if passwords match
            if password != confirm_password:
                self.add_error('confirm_password', "Passwords do not match.")
        else:
            # If password is empty but confirm_password has a value
            if confirm_password:
                self.add_error('password', "Please enter a password to confirm.")
        
        return cleaned_data

    def clean_username(self):
        """Validate username is unique and not empty"""
        username = self.cleaned_data.get('username')
        if not username:
            raise forms.ValidationError("Username is required.")
        
        # Check for duplicate username
        if self.instance and self.instance.pk:
            if User.objects.filter(username=username).exclude(pk=self.instance.pk).exists():
                raise forms.ValidationError("A user with this username already exists.")
        else:
            if User.objects.filter(username=username).exists():
                raise forms.ValidationError("A user with this username already exists.")
        return username

    def clean_email(self):
        """Validate email is unique and not empty"""
        email = self.cleaned_data.get('email')
        if not email:
            raise forms.ValidationError("Email is required.")
        
        # Check for duplicate email
        if self.instance and self.instance.pk:
            if User.objects.filter(email=email).exclude(pk=self.instance.pk).exists():
                raise forms.ValidationError("A user with this email already exists.")
        else:
            if User.objects.filter(email=email).exists():
                raise forms.ValidationError("A user with this email already exists.")
        return email

    def clean_mobile_number(self):
        """Validate that mobile number is exactly 10 digits"""
        mobile = self.cleaned_data.get('mobile_number')
        if not mobile:
            raise forms.ValidationError("Mobile number is required.")
        
        mobile_str = str(mobile)
        if not mobile_str.isdigit():
            raise forms.ValidationError("Phone number must contain only digits.")
        if len(mobile_str) != 10:
            raise forms.ValidationError("Phone number must be exactly 10 digits.")
        
        # Check for duplicate mobile number
        if self.instance and self.instance.pk:
            if User.objects.filter(mobile_number=mobile_str).exclude(pk=self.instance.pk).exists():
                raise forms.ValidationError("A user with this mobile number already exists.")
        else:
            if User.objects.filter(mobile_number=mobile_str).exists():
                raise forms.ValidationError("A user with this mobile number already exists.")
        return mobile_str

    def clean_employee_code(self):
        """Validate employee code format"""
        employee_code = self.cleaned_data.get('employee_code')
        if employee_code:
            # Check for duplicate employee code
            if self.instance and self.instance.pk:
                if User.objects.filter(employee_code=employee_code).exclude(pk=self.instance.pk).exists():
                    raise forms.ValidationError("Employee ID already exists.")
            else:
                if User.objects.filter(employee_code=employee_code).exists():
                    raise forms.ValidationError("Employee ID already exists.")
        return employee_code

    def clean_role(self):
        """Ensure SUPERADMIN role is not selected"""
        role = self.cleaned_data.get('role')
        if role and role.role_code == 'SUPERADMIN':
            raise forms.ValidationError("Cannot assign SUPERADMIN role.")
        return role
class RolePermissionForm(forms.ModelForm):

    permissions = forms.ModelMultipleChoiceField(
        queryset=Permissions.objects.order_by('display_order', 'name'),
        required=False,
        widget=forms.CheckboxSelectMultiple(
            attrs={
                'class': 'form-check-input',
            }
        ),
    )

    class Meta:
        model = Role

        fields = [
            'role_code',
            'role_name',
            'description',
            'is_active',
            'permissions',
        ]
        widgets = {
            'role_code': forms.TextInput(
                attrs={
                    'class': 'form-control',
                    'placeholder': 'Role code',
                }
            ),
            'role_name': forms.TextInput(
                attrs={
                    'class': 'form-control',
                    'placeholder': 'Role name',
                }
            ),
            'description': forms.Textarea(
                attrs={
                    'class': 'form-control',
                    'rows': 4,
                    'placeholder': 'Short role description',
                }
            ),
            'is_active': forms.CheckboxInput(
                attrs={
                    'class': 'form-check-input',
                }
            ),
        }


class DepartmentForm(forms.ModelForm):

    class Meta:
        model = Department
        fields = [
            'name',
            'code',
            'description',
            'is_active',
        ]
        widgets = {
            'name': forms.TextInput(
                attrs={
                    'class': 'form-control',
                    'placeholder': 'Department name',
                }
            ),
            'code': forms.TextInput(
                attrs={
                    'class': 'form-control',
                    'placeholder': 'DEPARTMENT CODE',
                }
            ),
            'description': forms.Textarea(
                attrs={
                    'class': 'form-control',
                    'rows': 5,
                    'placeholder': 'Short description',
                }
            ),
            'is_active': forms.CheckboxInput(
                attrs={
                    'class': 'form-check-input',
                }
            ),
        }

    def clean_code(self):
        code = (self.cleaned_data.get('code') or '').strip()
        return code.upper()
