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
from django.db.models import Q
from django.utils import timezone
from datetime import timedelta
from .forms import UserCreateForm, RolePermissionForm, DepartmentForm
from .models import User, Role, Department
from apps.accounts.models.permission import Permissions
from apps.companies.models import Company
from apps.organizations.models import Plant, Zone, Location, SubLocation


# -----------------------------------------------
# ============= LOGIN ===========================
# -----------------------------------------------

class LoginView(View):

    template_name = 'base/login.html'

    def get(self, request):
        return render(request,self.template_name)

    def post(self, request):

        username = (request.POST.get('username') or '').strip()
        password = request.POST.get('password')

        user = authenticate(request,username=username,password=password)
        if user:
            if not user.is_active:
                messages.error(
                    request,
                    'This account is inactive. Please contact the administrator.'
                )
                return render(request, self.template_name)

            login(request,user)
            user.is_online = True
            user.save()
            return redirect('accounts:dashboard')

        inactive_user = User.objects.filter(username=username).only('is_active').first()
        if inactive_user and not inactive_user.is_active:
            messages.error(
                request,
                'This account is inactive. Please contact the administrator.'
            )
            return render(request, self.template_name)

        messages.error(request,'Invalid Username or Password')

        return render(request,self.template_name)


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
    
# -----------------------------------------------
# ============= DASHBOARD =======================
# -----------------------------------------------

class DashboardView(LoginRequiredMixin,TemplateView):

    login_url = 'accounts:login'

    template_name = ('dashboard/dashboard.html')

    def get_context_data(self,**kwargs):

        context = super().get_context_data(**kwargs)

        context['user'] = (self.request.user)

        return context


# -----------------------------------------------
# ============= USER LIST =======================
# -----------------------------------------------

class UserListView(LoginRequiredMixin, ListView):

    model = User

    template_name = ('accounts/user_management/user_list.html')

    context_object_name = 'users'

    def get_queryset(self):
        user = self.request.user
        queryset = User.objects.select_related('role', 'company','department').order_by('-id')
        if not user.is_super_admin:
            queryset = queryset.filter(company=user.company)

        search = self.request.GET.get('search', '').strip()
        if search:
            queryset = queryset.filter(
                Q(full_name__icontains=search) |
                Q(username__icontains=search) |
                Q(email__icontains=search) |
                Q(mobile_number__icontains=search) |
                Q(employee_code__icontains=search) |
                Q(department__name__icontains=search) |
                Q(company__company_name__icontains=search)
            )

        return queryset

    def get_context_data(self, **kwargs):

        context = super().get_context_data(**kwargs)
        users = context['users']

        context['total_users_count'] = users.count()
        context['active_users_count'] = users.filter(is_active=True).count()

        return context

# ============= USER LIST =======================

class UserCreateView(LoginRequiredMixin, CreateView):

    model = User

    form_class = UserCreateForm

    template_name = ('accounts/user_management/user_create.html')

    success_url = reverse_lazy('accounts:user_list')

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        form.fields['is_active'].initial = False
        return form

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        # For super admins show all; for company users show only company-created plants
        if user.is_super_admin:
            company_plants = Plant.objects.filter(is_active=True)
        else:
            company_plants = Plant.objects.filter(created_by__company=user.company, is_active=True)

        context['company_plants'] = company_plants
        return context

    

    def form_valid(self, form):

        user = form.save(commit=False)

        if self.request.FILES.get('profile_image'):
            user.profile_image = self.request.FILES.get('profile_image')

        user.set_password(form.cleaned_data['password'])

        company_name = (self.request.POST.get('companyname') or '').strip()
        company = Company.objects.filter(
            Q(company_code__iexact=company_name) |
            Q(company_name__iexact=company_name)
        ).first()

        if company is None:
            company = Company.objects.order_by('id').first()

        if company is None:
            form.add_error(None, 'Please create a company before creating a user.')
            return self.form_invalid(form)

        user.company = company

        user.is_company_user = False

        user.save()

        messages.success(
            self.request,
            'User created successfully.'
        )

        return redirect(
            self.success_url
        )

    def form_invalid(self, form):

        print(form.errors)

        return super().form_invalid(form)
    

class UserUpdateView(LoginRequiredMixin, UpdateView):

    model = User

    form_class = UserCreateForm

    template_name = ('accounts/user_management/user_create.html')

    success_url = reverse_lazy('accounts:user_list')

    def get_context_data(self, **kwargs):

        context = super().get_context_data(**kwargs)

        context['page_title'] = 'Edit User'

        user = self.request.user
        if user.is_super_admin:
            company_plants = Plant.objects.filter(is_active=True)
        else:
            company_plants = Plant.objects.filter(created_by__company=user.company, is_active=True)

        context['company_plants'] = company_plants

        return context

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        form.fields['password'].required = False
        form.fields['confirm_password'].required = False
        return form

    def form_valid(self, form):
        with transaction.atomic():
            user = form.save(commit=False)

            if self.request.FILES.get('profile_image'):
                user.profile_image = self.request.FILES.get('profile_image')

            password = (form.cleaned_data.get('password') or '').strip()
            if password:
                user.set_password(password)

            user.save()

        messages.success(self.request, 'User updated successfully.')
        return redirect(self.success_url)


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
        return Role.objects.prefetch_related('permissions').order_by('role_name')


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
