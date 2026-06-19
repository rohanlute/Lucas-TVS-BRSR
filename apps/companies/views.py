from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect
from django.db import transaction
from django.urls import reverse_lazy
from django.utils.text import slugify
from django.views.generic import CreateView, DetailView, ListView, UpdateView, DeleteView
from django.views import View
from apps.accounts.mixins import SuperAdminRequiredMixin
from apps.accounts.models import *
from .forms import CompanyForm
from .models import *
from django.db.models import Q


# -----------------------------------------------
# ============= Company Management - Admin =======================
# -----------------------------------------------
class CompanyListView(LoginRequiredMixin, ListView):
    model = Company
    template_name = 'companies/company_list.html'
    context_object_name = 'companies'
    login_url = 'accounts:login'

    def get_queryset(self):
        user = self.request.user
        if user.role.role_code == 'SUPERADMIN':
            queryset = Company.objects.order_by('-created_at')
        else:
            queryset = Company.objects.filter(id=user.company_id).order_by('-created_at')

        search = self.request.GET.get('search', '').strip()
        if search:
            queryset = queryset.filter(
                Q(company_name__icontains=search) |
                Q(company_code__icontains=search) |
                Q(email__icontains=search) |
                Q(mobile_number__icontains=search) |
                Q(gst_number__icontains=search)
            )
        
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        if self.request.user.is_superuser:
            context['active_companies_count'] = Company.objects.filter(is_active=True).count()
        else:
            context['active_companies_count'] = Company.objects.filter(
                id=self.request.user.company_id,
                is_active=True
            ).count()

        return context


# ============= Company Management - Create =======================
class CompanyCreateView(LoginRequiredMixin, CreateView):
    model = Company
    form_class = CompanyForm
    template_name = 'companies/company_create.html'
    success_url = reverse_lazy('companies:company_list')
    login_url = 'accounts:login'

    def form_valid(self, form):
        password = (self.request.POST.get('password') or '').strip()
        confirm_password = (self.request.POST.get('confirm_password') or '').strip()

        if not password or not confirm_password:
            form.add_error(None, 'Password is required for the company admin.')
            return self.form_invalid(form)

        if password != confirm_password:
            form.add_error(None, 'Password and confirm password do not match.')
            return self.form_invalid(form)

        with transaction.atomic():
            company = form.save(commit=False)
            company.company_code = self._generate_company_code(
                form.cleaned_data['company_name']
            )

            profile_full_name = self.request.POST.get('profile_full_name', '').strip()
            profile_email = self.request.POST.get('profile_email', '').strip()
            profile_username = self.request.POST.get('profile_username', '').strip()
            profile_phone = self.request.POST.get('profile_phone', '').strip()
            profile_designation = self.request.POST.get('profile_designation', '').strip()
            profile_about = self.request.POST.get('profile_about', '').strip()

            company.contact_person = profile_full_name or company.company_name
            company.save()

            role, _ = Role.objects.get_or_create(
                role_code='COMPANYADMIN',
                defaults={
                    'role_name': 'Company Admin',
                    'description': 'Company administrator',
                }
            )
            if role.role_name != 'Company Admin':
                role.role_name = 'Company Admin'
                role.save(update_fields=['role_name'])

            username = profile_username or self._generate_company_username(company)
            if User.objects.filter(username=username).exists():
                username = self._generate_unique_username(username)

            user = User.objects.create_user(
                username=username,
                email=profile_email or company.email,
                password=password,
                full_name=profile_full_name or company.company_name,
                mobile_number=profile_phone or company.mobile_number,
                designation=profile_designation or None,
                about=profile_about or None,
                company=company,
                role=role,
                is_company_user=True,
            )

            profile_image = self.request.FILES.get('profile_image')
            if profile_image:
                user.profile_image = profile_image
                user.save(update_fields=['profile_image'])
            
            company.billing_address = self.request.POST.get('billing_address', '').strip() or None
            company.billing_zip_code = self.request.POST.get('billing_zip_code', '').strip() or None
            company.billing_country = self.request.POST.get('billing_country', '').strip() or None
            company.billing_state = self.request.POST.get('billing_state', '').strip() or None
            company.billing_city = self.request.POST.get('billing_city', '').strip() or None
            company.module_access_brsr = self.request.POST.get('module_access_brsr') == '1'
            company.module_access_gri = self.request.POST.get('module_access_gri') == '1'
            company.save(update_fields=[
                'contact_person',
                'billing_address',
                'billing_zip_code',
                'billing_country',
                'billing_state',
                'billing_city',
                'module_access_brsr',
                'module_access_gri',
            ])

            self.object = company

        messages.success(self.request, 'Company and company admin created successfully.')
        return redirect(self.get_success_url())

    def _generate_company_code(self, company_name):
        base_code = slugify(company_name).replace('-', '').upper()[:12] or 'COMPANY'
        company_code = base_code
        suffix = 1

        while Company.objects.filter(company_code=company_code).exists():
            suffix += 1
            suffix_text = str(suffix)
            company_code = f"{base_code[:20 - len(suffix_text)]}{suffix_text}"

        return company_code

    def _generate_company_username(self, company):
        base_username = slugify(company.company_name).replace('-', '').lower()[:20] or 'companyadmin'
        username = base_username
        suffix = 1

        while User.objects.filter(username=username).exists():
            suffix += 1
            suffix_text = str(suffix)
            username = f"{base_username[:150 - len(suffix_text)]}{suffix_text}"

        return username

    def _generate_unique_username(self, base_username):
        username = base_username
        suffix = 1

        while User.objects.filter(username=username).exists():
            suffix += 1
            suffix_text = str(suffix)
            username = f"{base_username[:150 - len(suffix_text)]}{suffix_text}"

        return username


# ============= Company Management - View =======================
class CompanyDetailView(LoginRequiredMixin, DetailView):
    model = Company
    template_name = 'companies/company_view.html'
    context_object_name = 'company'
    login_url = 'accounts:login'

class CompanyUpdateView(LoginRequiredMixin, UpdateView):
    template_name = 'companies/company_edit.html'
    model = Company
    form_class = CompanyForm
    context_object_name = 'company'
    login_url = 'accounts:login'
    success_url = reverse_lazy('companies:company_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['company_admin'] = User.objects.filter(company=self.object, is_company_user=True).first()
        return context

    def form_valid(self,form):
        password = (self.request.POST.get('password')or '').strip()
        confirm_password = (self.request.POST.get('confirm_password')or '').strip()

        with transaction.atomic():
            company = form.save(commit=False)
            profile_full_name = self.request.POST.get('profile_full_name', '').strip()
            profile_email = self.request.POST.get('profile_email', '').strip()
            profile_username = self.request.POST.get('profile_username', '').strip()
            profile_phone = self.request.POST.get('profile_phone', '').strip()
            profile_designation = self.request.POST.get('profile_designation', '').strip()
            profile_about = self.request.POST.get('profile_about', '').strip()

            company.contact_person = profile_full_name or company.company_name

            company.billing_address = self.request.POST.get('billing_address', '').strip() or None
            company.billing_zip_code = self.request.POST.get('billing_zip_code', '').strip() or None
            company.billing_country = self.request.POST.get('billing_country', '').strip() or None
            company.billing_state = self.request.POST.get('billing_state', '').strip() or None
            company.billing_city = self.request.POST.get('billing_city', '').strip() or None

            company.module_access_brsr = self.request.POST.get('module_access_brsr') == '1'
            company.module_access_gri = self.request.POST.get('module_access_gri') == '1'

            company.save()

            user = User.objects.filter(company=company, is_company_user=True).first()
            if user:
                if profile_username:
                    existing_user = User.objects.filter(username=profile_username).exclude(id=user.id).first()
                    if existing_user:
                        form.add_error('profile_username', 'This username is already taken by another user.')
                        return self.form_invalid(form)

                user.full_name = profile_full_name or company.company_name
                user.email = profile_email or company.email
                user.mobile_number = profile_phone or company.mobile_number
                user.designation = profile_designation or None
                user.about = profile_about or None

                profile_image = self.request.FILES.get('profile_image')
                if profile_image:
                    user.profile_image = profile_image
                
                if password:
                    if password != confirm_password:
                        form.add_error(None, 'Password and confirm password do not match.')
                        return self.form_invalid(form)
                    user.set_password(password)
                
                user.save()
            
            messages.success(self.request, 'Company and company admin updated successfully.')
            return redirect(self.get_success_url())

class CompanyDeleteView(LoginRequiredMixin, View):
    login_url = 'accounts:login'
    def post(self, request, pk):
        company = get_object_or_404(Company, pk=pk)
        try:
            with transaction.atomic():
                User.objects.filter(company=company).delete()
                company.delete()
            messages.success(request, f'{company.company_name} deleted successfully.')
        except Exception as e:
            messages.error(request,f'Unable to delete company: {str(e)}')
        return redirect('companies:company_list')