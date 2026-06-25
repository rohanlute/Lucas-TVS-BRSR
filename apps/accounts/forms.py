from django import forms
from .models import User, Role, Department
from apps.accounts.models.permission import Permissions
from apps.companies.models import Company


class UserCreateForm(forms.ModelForm):

    password = forms.CharField(
        widget=forms.PasswordInput(
            attrs={
                'class': 'form-control',
                'placeholder': 'Password',
                'id': 'passwordInput',
            }
        )
    )

    confirm_password = forms.CharField(
        widget=forms.PasswordInput(
            attrs={
                'class': 'form-control password',
                'placeholder': 'Password Confirm',
                'id': 'confirmPasswordInput',
            }
        )
    )

    role = forms.ModelChoiceField(
        queryset=Role.objects.order_by('role_name'),
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
                }
            ),
            'email': forms.EmailInput(
                attrs={
                    'class': 'form-control',
                    'placeholder': 'Email',
                    'id': 'mailInput',
                }
            ),
            'username': forms.TextInput(
                attrs={
                    'class': 'form-control',
                    'placeholder': 'Username',
                    'id': 'usernameInput',
                }
            ),
            'mobile_number': forms.NumberInput(
                attrs={
                    'class': 'form-control',
                    'placeholder': 'Phone',
                    'id': 'phoneInput',
                }
            ),
            'designation': forms.TextInput(
                attrs={
                    'class': 'form-control',
                    'placeholder': 'Designation',
                }
            ),
            'employee_code': forms.TextInput(
                attrs={
                    'class': 'form-control',
                    'placeholder': 'Employee ID',
                    'id': 'employee_codeInput',
                }
            ),
            'is_active': forms.CheckboxInput(
                attrs={
                    'class': 'form-check-input',
                }
            ),
        }

    def clean(self):

        cleaned_data = super().clean()

        password = cleaned_data.get('password')
        confirm_password = cleaned_data.get('confirm_password')

        if password != confirm_password:

            raise forms.ValidationError(
                'Passwords do not match.'
            )

        return cleaned_data

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
