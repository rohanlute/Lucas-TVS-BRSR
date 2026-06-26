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
from apps.organizations.models import Plant, Zone, Location, SubLocation
from apps.email_master.services import EmailService


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


class UserLocationAssignmentMixin:

    assignment_plant_name = 'assigned_plants'
    assignment_zone_name = 'assigned_zones'
    assignment_location_name = 'assigned_locations'
    assignment_sublocation_name = 'assigned_sublocations'

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
                'zones': set(),
                'locations': set(),
                'sublocations': set(),
            }

        return {
            'plants': set(user_obj.assigned_plants.values_list('id', flat=True)),
            'zones': set(user_obj.assigned_zones.values_list('id', flat=True)),
            'locations': set(user_obj.assigned_locations.values_list('id', flat=True)),
            'sublocations': set(user_obj.assigned_sublocations.values_list('id', flat=True)),
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

        zone_queryset = Zone.objects.filter(is_active=True)
        location_queryset = Location.objects.filter(is_active=True)
        sublocation_queryset = SubLocation.objects.filter(is_active=True)

        if user_obj:
            zone_queryset = zone_queryset.filter(Q(is_active=True) | Q(id__in=assigned_ids['zones']))
            location_queryset = location_queryset.filter(Q(is_active=True) | Q(id__in=assigned_ids['locations']))
            sublocation_queryset = sublocation_queryset.filter(Q(is_active=True) | Q(id__in=assigned_ids['sublocations']))

        return self.get_assignment_scope_plants(user_obj, company).prefetch_related(
            Prefetch(
                'zones',
                queryset=zone_queryset.prefetch_related(
                    Prefetch(
                        'locations',
                        queryset=location_queryset.prefetch_related(
                            Prefetch(
                                'sublocations',
                                queryset=sublocation_queryset
                            )
                        )
                    )
                )
            )
        )

    def _post_id_set(self, field_name):
        return {
            int(value)
            for value in self.request.POST.getlist(field_name)
            if str(value).isdigit()
        }

    def _expand_assignment_ids(self, plant_ids, zone_ids, location_ids, sublocation_ids):
        expanded_plants = set(plant_ids)
        expanded_zones = set(zone_ids)
        expanded_locations = set(location_ids)
        expanded_sublocations = set(sublocation_ids)

        zone_qs = Zone.objects.filter(id__in=expanded_zones).select_related('plant')
        location_qs = Location.objects.filter(id__in=expanded_locations).select_related('zone__plant')
        sublocation_qs = SubLocation.objects.filter(id__in=expanded_sublocations).select_related('location__zone__plant')

        expanded_plants.update(zone_qs.values_list('plant_id', flat=True))
        expanded_plants.update(location_qs.values_list('zone__plant_id', flat=True))
        expanded_plants.update(sublocation_qs.values_list('location__zone__plant_id', flat=True))

        expanded_zones.update(location_qs.values_list('zone_id', flat=True))
        expanded_zones.update(sublocation_qs.values_list('location__zone_id', flat=True))

        expanded_locations.update(sublocation_qs.values_list('location_id', flat=True))

        return {
            'plants': expanded_plants,
            'zones': expanded_zones,
            'locations': expanded_locations,
            'sublocations': expanded_sublocations,
        }

    def get_selected_assignment_ids(self, user_obj=None):
        if self.request.method == 'POST':
            return self._expand_assignment_ids(
                self._post_id_set(self.assignment_plant_name),
                self._post_id_set(self.assignment_zone_name),
                self._post_id_set(self.assignment_location_name),
                self._post_id_set(self.assignment_sublocation_name),
            )

        if user_obj:
            selected_plants = set(user_obj.assigned_plants.values_list('id', flat=True))
            selected_zones = set(user_obj.assigned_zones.values_list('id', flat=True))
            selected_locations = set(user_obj.assigned_locations.values_list('id', flat=True))
            selected_sublocations = set(user_obj.assigned_sublocations.values_list('id', flat=True))

            zone_qs = Zone.objects.filter(id__in=selected_zones).select_related('plant')
            location_qs = Location.objects.filter(id__in=selected_locations).select_related('zone__plant')
            sublocation_qs = SubLocation.objects.filter(id__in=selected_sublocations).select_related('location__zone__plant')

            selected_plants.update(zone_qs.values_list('plant_id', flat=True))
            selected_plants.update(location_qs.values_list('zone__plant_id', flat=True))
            selected_plants.update(sublocation_qs.values_list('location__zone__plant_id', flat=True))

            selected_zones.update(location_qs.values_list('zone_id', flat=True))
            selected_zones.update(sublocation_qs.values_list('location__zone_id', flat=True))

            selected_locations.update(sublocation_qs.values_list('location_id', flat=True))

            return {
                'plants': selected_plants,
                'zones': selected_zones,
                'locations': selected_locations,
                'sublocations': selected_sublocations,
            }

        return {
            'plants': set(),
            'zones': set(),
            'locations': set(),
            'sublocations': set(),
        }

    def get_assignment_context(self, user_obj=None):
        selected_ids = self.get_selected_assignment_ids(user_obj)
        company = self.get_selected_company_for_assignment()
        return {
            'company_plants': self.get_assignment_tree(user_obj, company),
            'selected_plant_ids': selected_ids['plants'],
            'selected_zone_ids': selected_ids['zones'],
            'selected_location_ids': selected_ids['locations'],
            'selected_sublocation_ids': selected_ids['sublocations'],
        }

    def sync_user_assignments(self, user_obj):
        company = self.get_selected_company_for_assignment()
        scope_plants = self.get_assignment_scope_plants(company=company)

        selected_ids = self._expand_assignment_ids(
            self._post_id_set(self.assignment_plant_name),
            self._post_id_set(self.assignment_zone_name),
            self._post_id_set(self.assignment_location_name),
            self._post_id_set(self.assignment_sublocation_name),
        )

        allowed_plants = set(
            scope_plants.filter(id__in=selected_ids['plants']).values_list('id', flat=True)
        )

        zone_qs = Zone.objects.filter(
            id__in=selected_ids['zones'],
            is_active=True,
            plant__in=scope_plants,
        ).select_related('plant')
        allowed_zones = set(zone_qs.values_list('id', flat=True))
        allowed_plants.update(zone_qs.values_list('plant_id', flat=True))

        location_qs = Location.objects.filter(
            id__in=selected_ids['locations'],
            is_active=True,
            zone__plant__in=scope_plants,
        ).select_related('zone__plant')
        allowed_locations = set(location_qs.values_list('id', flat=True))
        allowed_zones.update(location_qs.values_list('zone_id', flat=True))
        allowed_plants.update(location_qs.values_list('zone__plant_id', flat=True))

        sublocation_qs = SubLocation.objects.filter(
            id__in=selected_ids['sublocations'],
            is_active=True,
            location__zone__plant__in=scope_plants,
        ).select_related('location__zone__plant')
        allowed_sublocations = set(sublocation_qs.values_list('id', flat=True))
        allowed_locations.update(sublocation_qs.values_list('location_id', flat=True))
        allowed_zones.update(sublocation_qs.values_list('location__zone_id', flat=True))
        allowed_plants.update(sublocation_qs.values_list('location__zone__plant_id', flat=True))

        user_obj.assigned_plants.set(allowed_plants)
        user_obj.assigned_zones.set(allowed_zones)
        user_obj.assigned_locations.set(allowed_locations)
        user_obj.assigned_sublocations.set(allowed_sublocations)


# -----------------------------------------------
# ============= USER LIST =======================
# -----------------------------------------------

class UserListView(LoginRequiredMixin, ListView):

    model = User
    template_name = 'accounts/user_management/user_list.html'
    context_object_name = 'users'
    

    def get_queryset(self):
        user = self.request.user

        queryset = User.objects.select_related(
            'role', 'company', 'department'
        ).order_by('-id')

        if not user.is_super_admin:
            queryset = queryset.filter(company=user.company)

        search = self.request.GET.get('search', '').strip()
        status = self.request.GET.get('status', '').strip()
        role = self.request.GET.get('role', '').strip()

        if role:
            queryset = queryset.filter(role_id=role)
        else:
            super_admin_role = Role.objects.filter(role_code='SUPERADMIN').first()

            if super_admin_role:
                queryset = queryset.filter(role=super_admin_role)

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

        context['roles'] = Role.objects.order_by('role_name')
        context['selected_status'] = self.request.GET.get('status', '')
        selected_role = self.request.GET.get('role', '')

        if not selected_role:
            super_admin = Role.objects.filter(role_code='SUPERADMIN').first()

            if super_admin:
                selected_role = str(super_admin.id)

        context['selected_role'] = selected_role

        context['total_users_count'] = context['users'].count()
        context['active_users_count'] = context['users'].filter(is_active=True).count()

        return context


class UserCreateView(UserLocationAssignmentMixin, LoginRequiredMixin, CreateView):

    model = User

    form_class = UserCreateForm

    template_name = ('accounts/user_management/user_create.html')

    success_url = reverse_lazy('accounts:user_list')

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        form.fields['is_active'].initial = False
        self.configure_company_field(form)
        return form

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(self.get_assignment_context())
        return context

    

    def form_valid(self, form):

        with transaction.atomic():
            user = form.save(commit=False)

            if self.request.FILES.get('profile_image'):
                user.profile_image = self.request.FILES.get('profile_image')

            user.set_password(form.cleaned_data['password'])

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
    

class UserUpdateView(UserLocationAssignmentMixin, LoginRequiredMixin, UpdateView):

    model = User

    form_class = UserCreateForm

    template_name = ('accounts/user_management/user_create.html')

    success_url = reverse_lazy('accounts:user_list')

    def get_context_data(self, **kwargs):

        context = super().get_context_data(**kwargs)

        context['page_title'] = 'Edit User'
        context.update(self.get_assignment_context(self.object))

        return context

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        form.fields['password'].required = False
        form.fields['confirm_password'].required = False
        self.configure_company_field(form)
        return form

    def form_valid(self, form):
        with transaction.atomic():
            user = form.save(commit=False)

            if self.request.FILES.get('profile_image'):
                user.profile_image = self.request.FILES.get('profile_image')

            password = (form.cleaned_data.get('password') or '').strip()
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

            user.save()
            self.sync_user_assignments(user)

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
