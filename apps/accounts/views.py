from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.views import View
from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
from .mixins import *
from django.urls import reverse_lazy
from django.views.generic import (ListView,CreateView,UpdateView,DetailView,DeleteView)
from django.db import transaction
from django.db.models import Q, Prefetch
from django.utils import timezone
from datetime import timedelta
from .forms import UserCreateForm, RolePermissionForm, DepartmentForm
from .models import User, Role, Department
from apps.accounts.models.permission import Permissions
from apps.organizations.models import Plant
from apps.email_master.services import EmailService
from django.http import HttpResponseRedirect
from django.template.loader import render_to_string
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.contrib.auth.tokens import default_token_generator
from django.utils.encoding import force_bytes, force_str
from django.conf import settings


# -----------------------------------------------
# ============= LOGIN ===========================
# -----------------------------------------------

# accounts/views.py
from django.contrib.auth import authenticate, login
from django.utils import timezone
from django.shortcuts import render, redirect
from django.contrib import messages
from django.views import View
from django.contrib.auth import get_user_model

User = get_user_model()

class LoginView(View):
    template_name = 'base/login.html'

    def get(self, request):
        return render(request, self.template_name)

    def post(self, request):
        username = (request.POST.get('username') or '').strip()
        password = request.POST.get('password')
        
        if '@' in username:
            try:
                user_obj = User.objects.get(email__iexact=username)
                username = user_obj.username
            except User.DoesNotExist:
                pass
        
        user = authenticate(request, username=username, password=password)
        
        if user:
            if not user.is_active:
                messages.error(
                    request,
                    'This account is inactive. Please contact the administrator.'
                )
                return render(request, self.template_name)

            # Login the user
            login(request, user)
            
            # ✅ Update user's last_login
            user.last_login = timezone.now()
            user.is_online = True
            user.save(update_fields=['last_login', 'is_online'])
            
            # ✅ Update company's last_login (if user is a company admin)
            if user.is_company_user and user.company:
                user.company.last_login = user.last_login
                user.company.save(update_fields=['last_login'])
            
            messages.success(request, f'Welcome back, {user.get_full_name() or user.username}!')
            return redirect('accounts:dashboard')

        inactive_user = User.objects.filter(username=username).only('is_active').first()
        if inactive_user and not inactive_user.is_active:
            messages.error(
                request,
                'This account is inactive. Please contact the administrator.'
            )
            return render(request, self.template_name)

        messages.error(request, 'Invalid Username or Password')
        return render(request, self.template_name)

# -----------------------------------------------
# ============= LOGOUT ==========================
# -----------------------------------------------

class LogoutView(View):

    def get(self, request):
        request.user.is_online = False
        request.user.save()

        logout(request)

        messages.success(request,'Logged out successfully')

        return redirect('accounts:login')

class ForgotPasswordView(View):
    login_url = 'accounts:login'
    template_name = 'base/Forgot_pass.html'
    success_url = 'accounts:login'

    def get(self, request):
        return render(request, self.template_name)

    def post(self, request):
        email = (request.POST.get('email') or '').strip().lower()

        if not email:
            messages.error(request, 'Please enter your email address.')
            return render(request, self.template_name)

        try:
            user = User.objects.get(email__iexact=email)
        except User.DoesNotExist:
            messages.error(request, 'No account found with this email address.')
            return render(request, self.template_name)

        # Generate secure password reset token
        token = default_token_generator.make_token(user)
        # Encode user ID safely for use in the reset URL
        uid = urlsafe_base64_encode(force_bytes(user.pk))

        # Password reset link
        reset_url = request.build_absolute_uri(
            reverse_lazy('accounts:password_reset_confirm', kwargs={
                'uidb64': uid,
                'token': token
            })
        )
        # Send password reset email (HTML + plain text)
        context = {
            'user': user,
            'reset_url': reset_url,
            'site_name': 'BRSR',
            'full_name': user.full_name or user.username,
        }
        subject = 'Password Reset Request - BRSR'

        plain_message = f"""Hello {user.full_name or user.username},

We received a request to reset your password for your BRSR account.

Click the link below to reset your password:
{reset_url}

This link will expire in 24 hours.

If you didn't request this password reset, please ignore this email.

Best regards,
BRSR Team
"""

        try:
            EmailService.send_email(
                recipient=user,
                subject=subject,
                message=plain_message,
                html_template='emails/accounts/password_reset.html',
                context=context,
            )
            messages.success(request, 'Password reset link has been sent to your email.')
        except Exception:
            messages.error(request, 'Failed to send email. Please try again later.')
            return render(request, self.template_name)

        return HttpResponseRedirect(reverse_lazy(self.success_url))


class CustomPasswordResetConfirmView(View):
    '''Validate password reset link and update user's password'''

    template_name = 'base/password_reset_confirm.html'
    success_url = 'accounts:login'
    
    def get(self, request, uidb64, token):
        try:
            # Decode the encoded user ID from the URL
            uid = force_str(urlsafe_base64_decode(uidb64))
            user = User.objects.get(pk=uid)
        except (TypeError, ValueError, OverflowError, User.DoesNotExist):
            user = None
        
        # Verify that the reset token is still valid
        if user is not None and default_token_generator.check_token(user, token):
            return render(request, self.template_name, {
                'validlink': True,
                'uidb64': uidb64,
                'token': token,
            })
        else:
            return render(request, self.template_name, {
                'validlink': False,
            })
    
    def post(self, request, uidb64, token):
        try:
            # Retrieve user associated with the decoded ID
            uid = force_str(urlsafe_base64_decode(uidb64))
            user = User.objects.get(pk=uid)
        except (TypeError, ValueError, OverflowError, User.DoesNotExist):
            messages.error(request, 'Invalid reset link.')
            return HttpResponseRedirect(reverse_lazy('accounts:login'))
        
        # Verify that the reset token is still valid
        if not default_token_generator.check_token(user, token):
            messages.error(request, 'Invalid or expired reset link.')
            return HttpResponseRedirect(reverse_lazy('accounts:login'))
        
        password1 = request.POST.get('new_password1')
        password2 = request.POST.get('new_password2')
        
        if password1 != password2:
            messages.error(request, 'Passwords do not match.')
            return render(request, self.template_name, {
                'validlink': True,
                'uidb64': uidb64,
                'token': token,
            })
        
        if len(password1) < 8:
            messages.error(request, 'Password must be at least 8 characters.')
            return render(request, self.template_name, {
                'validlink': True,
                'uidb64': uidb64,
                'token': token,
            })
        
        user.set_password(password1)
        user.save()
        
        messages.success(request, 'Your password has been reset successfully. Please login with your new password.')
        return HttpResponseRedirect(reverse_lazy(self.success_url))

# -----------------------------------------------
# ============= DASHBOARD =======================
# -----------------------------------------------

class DashboardView(LoginRequiredMixin,TemplateView):

    login_url = 'accounts:login'

    template_name = ('dashboard/homepage.html')

    def get_context_data(self,**kwargs):

        context = super().get_context_data(**kwargs)

        context['user'] = (self.request.user)

        return context


class UserLocationAssignmentMixin:
    assignment_plant_name = 'assigned_plants'

    def can_choose_company(self):
        user = self.request.user
        return bool(user.is_superuser or user.is_super_admin)

    def configure_company_field(self, form):
        company_field = form.fields['company']
        user = self.request.user

        if self.can_choose_company():
            company_field.queryset = company_field.queryset.model.objects.filter(
                is_active=True
            ).order_by('company_name')
            company_field.required = True

            if self.request.method == 'GET' and getattr(self, 'object', None):
                form.initial.setdefault('company', self.object.company_id)
        else:
            company = getattr(user, 'company', None)
            company_field.queryset = company_field.queryset.model.objects.filter(
                pk=getattr(company, 'pk', None)
            )
            company_field.required = False
            company_field.disabled = True
            form.initial['company'] = getattr(company, 'pk', None)

    def get_assigned_ids(self, user_obj=None):
        if not user_obj:
            return {
                'plants': set(),
            }

        return {
            'plants': set(user_obj.assigned_plants.values_list('id', flat=True)),
        }

    def get_selected_company_for_assignment(self):
        """Get the company selected in the form for location assignment filtering"""
        if self.request.method == 'POST':
            company_id = self.request.POST.get('company')
            if company_id and str(company_id).isdigit():
                from apps.companies.models import Company
                return Company.objects.filter(id=int(company_id), is_active=True).first()
        
        if hasattr(self, 'object') and self.object:
            return self.object.company
        
        return getattr(self.request.user, 'company', None)

    def get_assignment_scope_plants(self, user_obj=None, company=None):
        user = self.request.user
        queryset = Plant.objects.filter(is_active=True)

        if company:
            queryset = queryset.filter(created_by__company=company)
        elif not user.is_super_admin:
            queryset = queryset.filter(created_by__company=user.company)

        if user_obj:
            assigned_ids = self.get_selected_assignment_ids(user_obj)['plants']
            queryset = queryset.filter(Q(is_active=True) | Q(id__in=assigned_ids))

        return queryset.distinct()

    def get_assignment_tree(self, user_obj=None, company=None):
        assigned_ids = self.get_selected_assignment_ids(user_obj)

        plant_queryset = Plant.objects.filter(is_active=True)

        if user_obj:
            plant_queryset = plant_queryset.filter(Q(is_active=True) | Q(id__in=assigned_ids['plants']))

        return self.get_assignment_scope_plants(user_obj, company)

    def _post_id_set(self, field_name):
        return {
            int(value)
            for value in self.request.POST.getlist(field_name)
            if str(value).isdigit()
        }

    def _expand_assignment_ids(self, plant_ids):
        expanded_plants = set(plant_ids)

        return {
            'plants': expanded_plants,
        }

    def get_selected_assignment_ids(self, user_obj=None):
        if self.request.method == 'POST':
            return self._expand_assignment_ids(
                self._post_id_set(self.assignment_plant_name),
            )

        if user_obj:
            selected_plants = set(user_obj.assigned_plants.values_list('id', flat=True))

            return {
                'plants': selected_plants,
            }

        return {
            'plants': set(),
        }

    def get_assignment_context(self, user_obj=None):
        selected_ids = self.get_selected_assignment_ids(user_obj)
        company = self.get_selected_company_for_assignment()
        return {
            'company_plants': self.get_assignment_tree(user_obj, company),
            'selected_plant_ids': selected_ids['plants'],
        }

    def sync_user_assignments(self, user_obj):
        company = self.get_selected_company_for_assignment()
        scope_plants = self.get_assignment_scope_plants(company=company)

        selected_ids = self._expand_assignment_ids(
            self._post_id_set(self.assignment_plant_name),
        )

        allowed_plants = set(
            scope_plants.filter(id__in=selected_ids['plants']).values_list('id', flat=True)
        )

        user_obj.assigned_plants.set(allowed_plants)


# -----------------------------------------------
# ============= USER LIST =======================
# -----------------------------------------------

class UserListView(LoginRequiredMixin, ListView):
    model = User
    template_name = 'accounts/user_management/user_list.html'
    context_object_name = 'users'
    paginate_by = 10

    def get_queryset(self):
        user = self.request.user
        queryset = User.objects.select_related(
            'role', 'company', 'department'
        ).order_by('-id')

        # ✅ Show only users from the same company (if not superadmin)
        if not user.is_super_admin:
            queryset = queryset.filter(company=user.company)

        search = self.request.GET.get('search', '').strip()
        status = self.request.GET.get('status', '').strip()
        role = self.request.GET.get('role', '').strip()

        # Apply role filter if specified
        if role:
            queryset = queryset.filter(role_id=role)

        if search:
            queryset = queryset.filter(
                Q(full_name__icontains=search) |
                Q(username__icontains=search) |
                Q(email__icontains=search) |
                Q(mobile_number__icontains=search)
            )

        if status == 'active':
            queryset = queryset.filter(is_active=True)
        elif status == 'inactive':
            queryset = queryset.filter(is_active=False)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # ✅ Exclude SUPERADMIN from filter dropdown
        context['roles'] = Role.objects.exclude(role_code='SUPERADMIN').order_by('role_name')
        
        context['selected_status'] = self.request.GET.get('status', '')
        context['selected_role'] = self.request.GET.get('role', '')
        
        # Get counts from the queryset
        users = self.get_queryset()
        context['total_users_count'] = users.count()
        context['active_users_count'] = users.filter(is_active=True).count()
        
        return context
# accounts/views.py
class UserCreateView(UserLocationAssignmentMixin, LoginRequiredMixin, CreateView):
    model = User
    form_class = UserCreateForm
    template_name = ('accounts/user_management/user_create.html')
    success_url = reverse_lazy('accounts:user_list')

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        form.fields['is_active'].initial = False
        
        # ✅ Remove SUPERADMIN from role choices
        if 'role' in form.fields:
            form.fields['role'].queryset = Role.objects.exclude(role_code='SUPERADMIN')
        
        # ✅ Configure company field
        self.configure_company_field(form)
        if self.request.user.is_super_admin:
            form.fields['role'].queryset = Role.objects.order_by('role_name')
        else:
            form.fields['role'].queryset = Role.objects.exclude(role_code='SUPERADMIN').order_by('role_name')

        return form

    def get_initial(self):
        initial = super().get_initial()
        # ✅ For new users, set all fields to empty
        if not self.object:
            initial['username'] = ''
            initial['password'] = ''
            initial['confirm_password'] = ''
            initial['full_name'] = ''
            initial['email'] = ''
            initial['mobile_number'] = ''
            initial['designation'] = ''
            initial['employee_code'] = ''
        return initial

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(self.get_assignment_context())
        return context

    def form_valid(self, form):
        with transaction.atomic():
            user = form.save(commit=False)

            if self.request.FILES.get('profile_image'):
                user.profile_image = self.request.FILES.get('profile_image')

            # ✅ Set password only if provided
            password = form.cleaned_data.get('password')
            if password:
                user.set_password(password)

            if self.can_choose_company():
                company = form.cleaned_data.get('company')
                if company is None:
                    form.add_error('company', 'Please select a company.')
                    return self.form_invalid(form)
                user.company = company
            else:
                company = getattr(self.request.user, 'company', None)
                if company is None:
                    form.add_error(None, 'Your account is not linked to a company.')
                    return self.form_invalid(form)
                user.company = company

            user.is_company_user = False
            user.save()
            self.sync_user_assignments(user)

            login_url = self.request.build_absolute_uri(reverse_lazy('accounts:login'))
            transaction.on_commit(lambda: EmailService.send_user_created_email(user, login_url=login_url))

        messages.success(self.request, 'User created successfully.')
        return redirect(self.success_url)

    def form_invalid(self, form):
        print(form.errors)
        return super().form_invalid(form)

class UserUpdateView(UserLocationAssignmentMixin, LoginRequiredMixin, UpdateView):
    model = User
    form_class = UserCreateForm
    template_name = ('accounts/user_management/user_create.html')

    def get_success_url(self):
        next_url = self.request.GET.get('next')
        if next_url:
            return next_url
        return reverse_lazy('accounts:user_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = 'Edit User'
        context.update(self.get_assignment_context(self.object))
        context['next_url'] = self.request.GET.get('next', reverse_lazy('accounts:user_list'))
        context['is_readonly'] = not self.request.user.is_company_admin
        return context

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        
        # Password is optional for updates
        form.fields['password'].required = False
        form.fields['confirm_password'].required = False
        form.fields['password'].help_text = "Leave blank to keep current password"
        form.fields['confirm_password'].help_text = "Leave blank to keep current password"
        
        # Configure company field
        self.configure_company_field(form)
        
        is_company_admin = self.request.user.is_company_admin
        
        if not is_company_admin:
            # Make fields read-only for non-company admins
            if 'role' in form.fields:
                form.fields['role'].disabled = True
                form.fields['role'].help_text = "This field is read-only for your role"
            
            if 'department' in form.fields:
                form.fields['department'].disabled = True
                form.fields['department'].help_text = "This field is read-only for your role"
            
            if 'company' in form.fields:
                form.fields['company'].disabled = True
                form.fields['company'].help_text = "This field is read-only for your role"
        
        # Ensure all fields are populated with existing data
        if self.object:
            form.fields['username'].initial = self.object.username
            form.fields['full_name'].initial = self.object.full_name
            form.fields['email'].initial = self.object.email
            form.fields['mobile_number'].initial = self.object.mobile_number
            form.fields['designation'].initial = self.object.designation
            form.fields['employee_code'].initial = self.object.employee_code
            form.fields['is_active'].initial = self.object.is_active
            form.fields['role'].initial = self.object.role_id
            form.fields['department'].initial = self.object.department_id
            form.fields['company'].initial = self.object.company_id
            
            if self.object.profile_image:
                form.fields['profile_image'].initial = self.object.profile_image
        
        return form

    def get_initial(self):
        initial = super().get_initial()
        
        if self.object:
            initial['username'] = self.object.username
            initial['full_name'] = self.object.full_name
            initial['email'] = self.object.email
            initial['mobile_number'] = self.object.mobile_number
            initial['designation'] = self.object.designation
            initial['employee_code'] = self.object.employee_code
            initial['is_active'] = self.object.is_active
            initial['role'] = self.object.role_id
            initial['department'] = self.object.department_id
            initial['company'] = self.object.company_id
            initial['password'] = ''
            initial['confirm_password'] = ''
        
        return initial

    def form_valid(self, form):
        with transaction.atomic():
            user = form.save(commit=False)

            if self.request.FILES.get('profile_image'):
                user.profile_image = self.request.FILES.get('profile_image')

            password = (form.cleaned_data.get('password') or '').strip()
            if password:
                user.set_password(password)

            # ✅ Handle company assignment - only if user is company admin
            if self.can_choose_company() or self.request.user.is_company_admin:
                company = form.cleaned_data.get('company')
                if company is None:
                    form.add_error('company', 'Please select a company.')
                    return self.form_invalid(form)
                user.company = company
            else:
                company = getattr(self.request.user, 'company', None)
                if company is None:
                    form.add_error(None, 'Your account is not linked to a company.')
                    return self.form_invalid(form)
                user.company = company

            user.save()
            self.sync_user_assignments(user)    
        messages.success(self.request, f'User "{user.get_full_name() or user.username}" updated successfully.')
        return redirect(self.get_success_url())

    def form_invalid(self, form):
        print(form.errors)
        return super().form_invalid(form)


class UserDetailView(LoginRequiredMixin, DetailView):

    model = User

    template_name = ('accounts/user_management/user_view.html')

    context_object_name = 'user_obj'

class UserDeleteView(LoginRequiredMixin, View):
    login_url = 'accounts:login'
    def post(self, request, pk):
        user = get_object_or_404(User, pk=pk)
        user.delete()
        messages.success(request, 'User deleted successfully.')
        return redirect('accounts:user_list')


class RolePermissionContextMixin:
    form_class = RolePermissionForm
    role_template_name = None

    def get_selected_permission_ids(self, role=None):
        if self.request.method == 'POST':
            return {
                int(permission_id)
                for permission_id in self.request.POST.getlist('permissions')
                if str(permission_id).isdigit()
            }

        if role:
            return set(role.permissions.values_list('pk', flat=True))

        return set()

    def get_role_form_context(self, form, role=None):
        context = {
            'form': form,
            'page_title': 'Role & Permission',
            'role_permissions': Permissions.objects.order_by('display_order', 'name'),
            'selected_permission_ids': self.get_selected_permission_ids(role),
            'is_edit': bool(role),
        }

        if role:
            context['editing_role'] = role

        return context

    def form_valid(self, form):
        role = form.save()
        messages.success(self.request, f"Role '{role.role_name}' saved successfully.")
        return redirect(self.get_success_url())


class RoleListView(LoginRequiredMixin, ListView):
    model = Role
    template_name = 'accounts/user_management/role_list.html'
    context_object_name = 'roles'

    def get_queryset(self):
        queryset = Role.objects.prefetch_related('permissions').order_by('role_name')
        if not self.request.user.is_super_admin:
            queryset = queryset.exclude(role_code='SUPERADMIN')
        return queryset


class RoleCreateView(RolePermissionContextMixin, LoginRequiredMixin, CreateView):
    model = Role
    form_class = RolePermissionForm

    template_name = 'accounts/user_management/role_create.html'

    success_url = reverse_lazy('accounts:role_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(self.get_role_form_context(context['form']))
        return context

    def form_valid(self, form):
        role = form.save()
        messages.success(self.request, f"Role '{role.role_name}' created successfully.")
        return redirect(self.success_url)


class RoleUpdateView(RolePermissionContextMixin, LoginRequiredMixin, UpdateView):

    model = Role

    form_class = RolePermissionForm

    template_name = 'accounts/user_management/role_edit.html'

    success_url = reverse_lazy('accounts:role_list')

    def get_queryset(self):
        return Role.objects.prefetch_related('permissions')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(self.get_role_form_context(context['form'], self.object))
        return context

    def form_valid(self, form):
        role = form.save()
        messages.success(self.request, f"Role '{role.role_name}' updated successfully.")
        return redirect(self.success_url)
    
# -----------------------------------------------
# ============= Department =======================
# -----------------------------------------------

class DepartmentListView(LoginRequiredMixin, TemplateView):

    login_url = 'accounts:login'

    template_name = ('accounts/department/department_list.html')

    def get_queryset(self):
        queryset = Department.objects.order_by('-created_at')
        search = self.request.GET.get('search', '').strip()
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) |
                Q(code__icontains=search) |
                Q(description__icontains=search)
            )
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        departments = self.get_queryset()
        cutoff = timezone.now() - timedelta(days=30)

        context['departments'] = departments
        context['total_departments_count'] = Department.objects.count()
        context['active_departments_count'] = Department.objects.filter(is_active=True).count()
        context['inactive_departments_count'] = Department.objects.filter(is_active=False).count()
        context['new_departments_count'] = Department.objects.filter(created_at__gte=cutoff).count()
        context['search_query'] = self.request.GET.get('search', '').strip()

        return context


class DepartmentCreateView(LoginRequiredMixin, CreateView):

    login_url = 'accounts:login'

    model = Department
    form_class = DepartmentForm
    template_name = ('accounts/department/department_create.html')
    success_url = reverse_lazy('accounts:department_list')

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        form.fields['is_active'].initial = True
        return form

    def form_valid(self, form):
        department = form.save()
        messages.success(self.request, f'Department "{department.name}" created successfully.')
        return redirect(self.success_url)


class DepartmentDetailView(LoginRequiredMixin, DetailView):

    login_url = 'accounts:login'
    model = Department
    template_name = ('accounts/department/department_view.html')
    context_object_name = 'department'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['employee_count'] = self.object.employee_count
        context['active_employee_count'] = self.object.active_employee_count
        return context


class DepartmentUpdateView(LoginRequiredMixin, UpdateView):

    login_url = 'accounts:login'
    model = Department
    form_class = DepartmentForm
    template_name = ('accounts/department/department_edit.html')
    context_object_name = 'department'
    success_url = reverse_lazy('accounts:department_list')

    def form_valid(self, form):
        department = form.save()
        messages.success(self.request, f'Department "{department.name}" updated successfully.')
        return redirect(self.success_url)


class DepartmentDeleteView(LoginRequiredMixin, DeleteView):

    login_url = 'accounts:login'

    model = Department
    template_name = ('accounts/department/department_delete.html')
    context_object_name = 'department'
    success_url = reverse_lazy('accounts:department_list')

    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        department_name = self.object.name
        response = super().delete(request, *args, **kwargs)
        messages.success(request, f'Department "{department_name}" deleted successfully.')
        return response
    
# accounts/views.py - Updated BRSR Views

class BRSRDashboardView(TemplateView):
    """
    Renders the BRSR (Business Responsibility & Sustainability Report) 
    project overview page with ESG framework information.
    """
    template_name = "dashboard/homepage.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        from apps.organizations.models import FinancialYear
        
        # Get current date
        today = timezone.now().date()
        
        # Get current financial year from database (based on dates)
        current_fy = FinancialYear.objects.filter(
            start_date__lte=today,
            end_date__gte=today
        ).first()
        
        # If no current financial year found, get the latest one
        if not current_fy:
            current_fy = FinancialYear.objects.order_by('-start_date').first()
        
        # Set financial year display name
        if current_fy:
            # Use the financial_year field which stores "2022-2023" format
            context['current_fy'] = current_fy.financial_year
        else:
            # Fallback if no financial year exists
            current_year = timezone.now().year
            context['current_fy'] = f"{current_year-1}-{current_year}"
        
        # Also pass the full financial year object for other uses
        context['current_fy_obj'] = current_fy
        
        # Get current year for display
        current_year = timezone.now().year
        context['current_year'] = current_year
        
        # Get company name from user if available
        company_name = None
        if self.request.user.is_authenticated:
            try:
                if hasattr(self.request.user, 'company') and self.request.user.company:
                    company_name = self.request.user.company.company_name
            except:
                pass
        
        context['company_name'] = company_name or 'Your Company'
        context['total_companies'] = 1000  # Static value for display
        
        # ESG Score data for the ring chart
        context['esg_breakdown'] = {
            'environment': 38,
            'social': 30,
            'governance': 32,
            'total': 100
        }
        
        # NGRBC Principles data
        context['ngrbc_principles'] = [
            {
                'id': 1,
                'code': 'P1',
                'title': 'Ethics, transparency & accountability',
                'description': 'Businesses conduct themselves ethically and are accountable to stakeholders.',
                'icon': 'fa-shield-alt'
            },
            {
                'id': 2,
                'code': 'P2',
                'title': 'Safe & sustainable goods',
                'description': 'Products and services are safe and sustainable across their full lifecycle.',
                'icon': 'fa-recycle'
            },
            {
                'id': 3,
                'code': 'P3',
                'title': 'Employee wellbeing',
                'description': 'Businesses respect and promote the wellbeing of all employees, including value-chain workers.',
                'icon': 'fa-users'
            },
            {
                'id': 4,
                'code': 'P4',
                'title': 'Stakeholder interests',
                'description': 'Businesses respect the interests of, and are responsive to, all stakeholders.',
                'icon': 'fa-handshake'
            },
            {
                'id': 5,
                'code': 'P5',
                'title': 'Human rights',
                'description': 'Businesses respect and promote human rights across their operations.',
                'icon': 'fa-gavel'
            },
            {
                'id': 6,
                'code': 'P6',
                'title': 'Environmental protection',
                'description': 'Businesses respect and make efforts to protect and restore the environment.',
                'icon': 'fa-leaf'
            },
            {
                'id': 7,
                'code': 'P7',
                'title': 'Responsible advocacy',
                'description': 'Policy engagement and advocacy are conducted in a responsible manner.',
                'icon': 'fa-bullhorn'
            },
            {
                'id': 8,
                'code': 'P8',
                'title': 'Inclusive growth',
                'description': 'Businesses support equitable development and inclusive growth for all.',
                'icon': 'fa-chart-line'
            },
            {
                'id': 9,
                'code': 'P9',
                'title': 'Consumer value',
                'description': 'Businesses engage with and provide value to consumers responsibly.',
                'icon': 'fa-shopping-bag'
            }
        ]
        
        # BRSR Report Structure
        context['report_structure'] = [
            {
                'section': 'A',
                'title': 'General Disclosures',
                'description': 'Company identity, products, operations, employees and value-chain details that set the reporting context.',
                'meta': 'ENTITY-LEVEL PROFILE'
            },
            {
                'section': 'B',
                'title': 'Management & Process',
                'description': 'Governance structure, policies and processes the company has in place to act on each NGRBC principle.',
                'meta': 'POLICY & OVERSIGHT'
            },
            {
                'section': 'C',
                'title': 'Principle-wise Performance',
                'description': 'Quantified Essential and Leadership indicators reported against each of the nine NGRBC principles.',
                'meta': 'ESSENTIAL + LEADERSHIP'
            }
        ]
        
        # FAQ Data
        context['faqs'] = [
            {
                'question': 'Who is required to file a BRSR?',
                'answer': 'SEBI mandates BRSR filing for the top 1,000 listed companies by market capitalisation, as part of their annual report from FY 2022–23 onward. Other listed entities may file it voluntarily.',
                'open': True
            },
            {
                'question': 'How is BRSR different from the old BRR?',
                'answer': 'The earlier Business Responsibility Report was largely descriptive and qualitative. BRSR replaces it with quantifiable, indicator-based disclosures that can be compared across companies and years.',
                'open': False
            },
            {
                'question': 'What\'s the difference between Essential and Leadership indicators?',
                'answer': 'Essential indicators are mandatory for every applicable company. Leadership indicators are recommended, more advanced disclosures for companies pursuing stronger ESG performance.',
                'open': False
            },
            {
                'question': 'Does BRSR replace financial reporting?',
                'answer': 'No. BRSR sits alongside financial statements as a non-financial, ESG-focused disclosure — it doesn\'t substitute for statutory financial reporting requirements.',
                'open': False
            }
        ]
        
        # Stats for hero section
        context['hero_stats'] = [
            {'value': '1,000+', 'label': 'LISTED COMPANIES'},
            {'value': '9', 'label': 'CORE PRINCIPLES'},
            {'value': '3', 'label': 'REPORT SECTIONS'},
            {'value': 'FY 22–23', 'label': 'MANDATORY FROM'}
        ]
        
        # Why BRSR cards
        context['why_brsr'] = [
            {
                'icon': 'fa-shield-alt',
                'title': 'Regulatory compliance',
                'description': 'Meets SEBI\'s mandatory disclosure norms for listed companies, avoiding penalties and filing delays.'
            },
            {
                'icon': 'fa-chart-pie',
                'title': 'Investor confidence',
                'description': 'Gives investors decision-useful, comparable ESG data instead of scattered sustainability claims.'
            },
            {
                'icon': 'fa-exclamation-triangle',
                'title': 'Risk visibility',
                'description': 'Surfaces environmental and social risks in the reporting cycle, before they turn into financial ones.'
            },
            {
                'icon': 'fa-eye',
                'title': 'Transparency & trust',
                'description': 'Builds credibility with regulators, customers and communities through verifiable, public disclosure.'
            },
            {
                'icon': 'fa-globe',
                'title': 'Global alignment',
                'description': 'Maps cleanly onto GRI, BRSR Core and other international ESG standards for cross-border reporting.'
            },
            {
                'icon': 'fa-chart-line',
                'title': 'Long-term value',
                'description': 'Turns sustainability commitments into a trackable, year-on-year record rather than one-off claims.'
            }
        ]
        
        # User assignments (mock data)
        if self.request.user.is_authenticated:
            context['user_assignments'] = 2  # Mock count
        else:
            context['user_assignments'] = 0
        
        return context

    def get(self, request, *args, **kwargs):
        # Check if PDF download is requested
        if request.GET.get('download_pdf'):
            pdf_buffer = generate_brsr_pdf_report(
                company_name=request.user.company.company_name if request.user.is_authenticated and hasattr(request.user, 'company') else None,
                user=request.user,
            )
            
            timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
            filename = f"brsr_overview_report_{timestamp}.pdf"
            
            response = HttpResponse(pdf_buffer.getvalue(), content_type='application/pdf')
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            return response
        
        return super().get(request, *args, **kwargs)


class BRSRPrincipleDetailView(TemplateView):
    """
    Detailed view for a specific NGRBC principle
    """
    template_name = "brsr/principle_detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        from apps.organizations.models import FinancialYear
        
        # Get current financial year
        today = timezone.now().date()
        current_fy = FinancialYear.objects.filter(
            start_date__lte=today,
            end_date__gte=today
        ).first()
        
        if not current_fy:
            current_fy = FinancialYear.objects.order_by('-start_date').first()
        
        if current_fy:
            context['current_fy'] = current_fy.financial_year
        else:
            current_year = timezone.now().year
            context['current_fy'] = f"{current_year-1}-{current_year}"
        
        principle_id = int(self.kwargs.get('principle_id', 1))
        
        # Define all principles with detailed information
        principles = {
            1: {
                'id': 1,
                'code': 'P1',
                'title': 'Ethics, transparency & accountability',
                'short_description': 'Businesses conduct themselves ethically and are accountable to stakeholders.',
                'description': 'Businesses should conduct and govern themselves with Ethics, Transparency and Accountability. This principle requires companies to operate in a manner that is fair, transparent and accountable to all stakeholders.',
                'indicators': [
                    {'name': 'Ethics Policy', 'essential': True, 'description': 'Policy on ethical conduct'},
                    {'name': 'Whistleblower Mechanism', 'essential': True, 'description': 'Channel for reporting unethical behavior'},
                    {'name': 'Anti-Corruption Measures', 'essential': False, 'description': 'Anti-bribery and corruption policies'},
                    {'name': 'Transparency Reports', 'essential': False, 'description': 'Regular disclosure of business practices'}
                ],
                'related_sdgs': ['SDG 16', 'SDG 17']
            },
            # ... rest of the principles remain the same
        }
        
        context['principle'] = principles.get(principle_id, principles[1])
        context['principle_id'] = principle_id
        context['total_principles'] = len(principles)
        
        return context


class BRSRReportView(TemplateView):
    """
    View for generating/ viewing a BRSR report
    """
    template_name = "brsr/report.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        from apps.organizations.models import FinancialYear
        
        # Get current date
        today = timezone.now().date()
        
        # Get current financial year from database
        current_fy = FinancialYear.objects.filter(
            start_date__lte=today,
            end_date__gte=today
        ).first()
        
        if not current_fy:
            current_fy = FinancialYear.objects.order_by('-start_date').first()
        
        # Set financial year display
        if current_fy:
            context['current_fy'] = current_fy.financial_year
        else:
            current_year = timezone.now().year
            context['current_fy'] = f"{current_year-1}-{current_year}"
        
        # Get report data
        context['report_date'] = timezone.now()
        context['report_id'] = f"BRSR-{timezone.now().strftime('%Y')}-001"
        
        # Get company name from user if available
        company_name = None
        if self.request.user.is_authenticated:
            try:
                if hasattr(self.request.user, 'company') and self.request.user.company:
                    company_name = self.request.user.company.company_name
            except:
                pass
        
        context['company_name'] = company_name or 'Your Company'
        
        # Report sections with completion status
        context['sections'] = [
            {
                'id': 'section_a',
                'name': 'General Disclosures',
                'description': 'Company identity, products, operations, employees and value-chain details',
                'completed': True,
                'completion_pct': 100
            },
            {
                'id': 'section_b',
                'name': 'Management & Process',
                'description': 'Governance structure, policies and processes for ESG oversight',
                'completed': False,
                'completion_pct': 65
            },
            {
                'id': 'section_c',
                'name': 'Principle-wise Performance',
                'description': 'Quantified indicators against the nine NGRBC principles',
                'completed': False,
                'completion_pct': 42
            }
        ]
        
        # Overall completion
        total_pct = sum(s['completion_pct'] for s in context['sections']) / len(context['sections'])
        context['overall_completion'] = round(total_pct)
        
        # Principle status for Section C
        context['principle_status'] = [
            {'code': 'P1', 'name': 'Ethics & Accountability', 'status': 'Complete', 'pct': 100},
            {'code': 'P2', 'name': 'Safe & Sustainable Goods', 'status': 'Partial', 'pct': 70},
            {'code': 'P3', 'name': 'Employee Wellbeing', 'status': 'Partial', 'pct': 60},
            {'code': 'P4', 'name': 'Stakeholder Interests', 'status': 'In Progress', 'pct': 45},
            {'code': 'P5', 'name': 'Human Rights', 'status': 'In Progress', 'pct': 30},
            {'code': 'P6', 'name': 'Environmental Protection', 'status': 'Pending', 'pct': 0},
            {'code': 'P7', 'name': 'Responsible Advocacy', 'status': 'Pending', 'pct': 0},
            {'code': 'P8', 'name': 'Inclusive Growth', 'status': 'Pending', 'pct': 0},
            {'code': 'P9', 'name': 'Consumer Value', 'status': 'Pending', 'pct': 0}
        ]
        
        return context
class BRSRDataAPIView(TemplateView):
    """
    API endpoint for fetching BRSR data for AJAX requests
    """
    def get(self, request):
        try:
            data = {
                'success': True,
                'principles': [
                    {
                        'id': i,
                        'code': f'P{i}',
                        'title': f'Principle {i}',
                        'description': f'Description for principle {i}'
                    }
                    for i in range(1, 10)
                ],
                'stats': {
                    'total_companies': 1000,
                    'reporting_rate': 72,
                    'compliance_score': 68
                }
            }
            return HttpResponse(
                json.dumps(data),
                content_type='application/json'
            )
        except Exception as e:
            return HttpResponse(
                json.dumps({
                    'success': False,
                    'error': str(e)
                }),
                content_type='application/json',
                status=500
            )


from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator

@method_decorator(csrf_exempt, name='dispatch')
class BRSRReportGenerateView(TemplateView):
    """
    Generate a BRSR report from form data
    """
    def post(self, request):
        try:
            data = json.loads(request.body)
            
            # Get company name
            company_name = None
            if request.user.is_authenticated:
                try:
                    if hasattr(request.user, 'company') and request.user.company:
                        company_name = request.user.company.company_name
                except:
                    pass
            
            # Generate report ID
            report_id = f"BRSR-{timezone.now().strftime('%Y%m%d')}-{timezone.now().strftime('%H%M')}"
            
            return HttpResponse(
                json.dumps({
                    'success': True,
                    'message': 'Report generated successfully',
                    'report_id': report_id,
                    'company_name': company_name or 'Your Company'
                }),
                content_type='application/json'
            )
        except Exception as e:
            return HttpResponse(
                json.dumps({
                    'success': False,
                    'error': str(e)
                }),
                content_type='application/json',
                status=400
            )


# ===== PDF GENERATOR SERVICE =====
# This can be in a separate file: apps/brsr/services/pdf_generator.py

from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import inch
from django.utils import timezone


def generate_brsr_pdf_report(company_name=None, user=None):
    """
    Generate a PDF report for BRSR overview
    """
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    styles = getSampleStyleSheet()
    story = []
    
    # Title
    title_style = ParagraphStyle(
        'TitleStyle',
        parent=styles['Title'],
        fontSize=24,
        spaceAfter=12,
        alignment=1  # Center
    )
    story.append(Paragraph("BRSR Overview Report", title_style))
    story.append(Spacer(1, 12))
    
    # Company name
    if company_name:
        story.append(Paragraph(f"Company: {company_name}", styles['Normal']))
    else:
        story.append(Paragraph("Company: Not specified", styles['Normal']))
    
    story.append(Paragraph(f"Date: {timezone.now().strftime('%B %d, %Y')}", styles['Normal']))
    story.append(Spacer(1, 24))
    
    # Overview
    heading_style = ParagraphStyle(
        'HeadingStyle',
        parent=styles['Heading2'],
        fontSize=16,
        spaceAfter=8,
        spaceBefore=12
    )
    story.append(Paragraph("Overview", heading_style))
    story.append(Paragraph(
        "This report provides an overview of the Business Responsibility and Sustainability Reporting (BRSR) framework. "
        "BRSR is India's standard for ESG disclosure, mandated by SEBI for listed companies.",
        styles['Normal']
    ))
    story.append(Spacer(1, 16))
    
    # Report Structure
    story.append(Paragraph("Report Structure", heading_style))
    
    structure_data = [
        ['Section', 'Title', 'Description'],
        ['A', 'General Disclosures', 'Company profile and operations'],
        ['B', 'Management & Process', 'Governance and policies'],
        ['C', 'Principle-wise Performance', 'ESG indicators by principle']
    ]
    
    table = Table(structure_data, colWidths=[0.8*inch, 2*inch, 3*inch])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    story.append(table)
    story.append(Spacer(1, 24))
    
    # Nine Principles
    story.append(Paragraph("Nine NGRBC Principles", heading_style))
    
    principles = [
        "P1: Ethics, transparency & accountability",
        "P2: Safe & sustainable goods",
        "P3: Employee wellbeing",
        "P4: Stakeholder interests",
        "P5: Human rights",
        "P6: Environmental protection",
        "P7: Responsible advocacy",
        "P8: Inclusive growth",
        "P9: Consumer value"
    ]
    
    for p in principles:
        story.append(Paragraph(f"• {p}", styles['Normal']))
    
    doc.build(story)
    buffer.seek(0)
    return buffer