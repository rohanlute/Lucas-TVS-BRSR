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
from django.utils import timezone
from django.http import JsonResponse
from .models import State, City


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
# companies/views.py
class CompanyCreateView(LoginRequiredMixin, CreateView):
    model = Company
    form_class = CompanyForm
    template_name = 'companies/company_create.html'
    success_url = reverse_lazy('companies:company_list')
    login_url = 'accounts:login'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["countries"] = Country.objects.filter(is_active=True).order_by("name")
        context["is_superadmin"] = self.request.user.is_superuser
        return context

    def form_valid(self, form):
        password = form.cleaned_data.get('password')
        confirm_password = form.cleaned_data.get('confirm_password')

        if not password or not confirm_password:
            form.add_error(None, 'Password is required for the company admin.')
            return self.form_invalid(form)

        if password != confirm_password:
            form.add_error(None, 'Password and confirm password do not match.')
            return self.form_invalid(form)

        with transaction.atomic():
            profile_full_name = self.request.POST.get('profile_full_name', '').strip()
            profile_email = self.request.POST.get('profile_email', '').strip()
            profile_username = self.request.POST.get('profile_username', '').strip()
            profile_phone = self.request.POST.get('profile_phone', '').strip()
            profile_designation = self.request.POST.get('profile_designation', '').strip()
            profile_about = self.request.POST.get('profile_about', '').strip()
            
            company = form.save(commit=False)
            company.contact_person = profile_full_name or company.company_name

            billing_country = form.cleaned_data.get('billing_country')
            billing_state = form.cleaned_data.get('billing_state')
            billing_city = form.cleaned_data.get('billing_city')
            
            company.billing_address = form.cleaned_data.get('billing_address', '')
            company.billing_zip_code = form.cleaned_data.get('billing_zip_code', '')
            company.billing_country_id = billing_country.id if billing_country else None
            company.billing_state_id = billing_state.id if billing_state else None
            company.billing_city_id = billing_city.id if billing_city else None

            company.company_code = self._generate_company_code(
                form.cleaned_data['company_name']
            )
            
            # ✅ Set initial last_login
            company.last_login = timezone.now()

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

            # ✅ Set user's last_login
            user.last_login = timezone.now()
            user.save(update_fields=['last_login'])

            # ✅ Update company's last_login to match user (already set above)
            company.last_login = user.last_login
            company.save(update_fields=['last_login'])

            profile_image = self.request.FILES.get('profile_image')
            if profile_image:
                user.profile_image = profile_image
                user.save(update_fields=['profile_image'])
        
            self.object = company

        messages.success(self.request, 'Company and company admin created successfully.')
        return redirect(self.get_success_url())

    def form_invalid(self, form):
        context = self.get_context_data()
        context['form'] = form
        return self.render_to_response(context)

    def _generate_company_code(self, company_name):
        from django.utils.text import slugify
        
        base_code = slugify(company_name).replace('-', '').upper()[:12] or 'COMPANY'
        company_code = base_code
        suffix = 1

        while Company.objects.filter(company_code=company_code).exists():
            suffix += 1
            suffix_text = str(suffix)
            company_code = f"{base_code[:20 - len(suffix_text)]}{suffix_text}"

        return company_code

    def _generate_company_username(self, company):
        from django.utils.text import slugify
        
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
        context["countries"] = Country.objects.filter(is_active=True).order_by("name")
        
        company = self.object
        
        if company.billing_country_id:
            context["states"] = State.objects.filter(
                country_id=company.billing_country_id,
                is_active=True
            ).order_by("name")
        else:
            context["states"] = State.objects.none()
        
        if company.billing_state_id:
            context["cities"] = City.objects.filter(
                state_id=company.billing_state_id,
                is_active=True
            ).order_by("name")
        else:
            context["cities"] = City.objects.none()
        
        context["billing_address"] = company.billing_address or ''
        context["billing_zip_code"] = company.billing_zip_code or ''
        context["billing_country_id"] = company.billing_country_id
        context["billing_state_id"] = company.billing_state_id
        context["billing_city_id"] = company.billing_city_id
        
        return context

    def get_initial(self):
        """Pre-populate form with existing data"""
        initial = super().get_initial()
        company = self.object
        
        initial['company_name'] = company.company_name
        initial['email'] = company.email
        initial['mobile_number'] = company.mobile_number
        initial['website'] = company.website
        initial['gst_number'] = company.gst_number
        initial['cin_number'] = company.cin_number
        initial['date_of_incorporation'] = company.date_of_incorporation
        initial['contact_person'] = company.contact_person
        initial['billing_address'] = company.billing_address
        initial['billing_zip_code'] = company.billing_zip_code
        initial['billing_country'] = company.billing_country_id
        initial['billing_state'] = company.billing_state_id
        initial['billing_city'] = company.billing_city_id
        initial['about_company'] = company.about_company
        initial['listed_company'] = company.listed_company
        initial['is_active'] = company.is_active
        
        # ✅ Ensure password fields are always empty
        initial['password'] = ''
        initial['confirm_password'] = ''
        
        return initial

    def form_valid(self, form):
        password = (self.request.POST.get('password') or '').strip()
        confirm_password = (self.request.POST.get('confirm_password') or '').strip()

        with transaction.atomic():
            company = form.save(commit=False)
            
            profile_full_name = self.request.POST.get('profile_full_name', '').strip()
            profile_email = self.request.POST.get('profile_email', '').strip()
            profile_username = self.request.POST.get('profile_username', '').strip()
            profile_phone = self.request.POST.get('profile_phone', '').strip()
            profile_designation = self.request.POST.get('profile_designation', '').strip()
            profile_about = self.request.POST.get('profile_about', '').strip()

            if profile_full_name:
                company.contact_person = profile_full_name

            # Get billing data - use cleaned data from form
            company.billing_address = form.cleaned_data.get('billing_address', '')
            company.billing_zip_code = form.cleaned_data.get('billing_zip_code', '')
            
            billing_country = form.cleaned_data.get('billing_country')
            billing_state = form.cleaned_data.get('billing_state')
            billing_city = form.cleaned_data.get('billing_city')
            
            company.billing_country_id = billing_country.id if billing_country else None
            company.billing_state_id = billing_state.id if billing_state else None
            company.billing_city_id = billing_city.id if billing_city else None

            company.save()

            user = User.objects.filter(company=company, is_company_user=True).first()
            if user:
                if profile_username:
                    existing_user = User.objects.filter(username=profile_username).exclude(id=user.id).first()
                    if existing_user:
                        form.add_error('profile_username', 'This username is already taken by another user.')
                        return self.form_invalid(form)

                # Update user fields
                if profile_full_name:
                    user.full_name = profile_full_name
                if profile_email:
                    user.email = profile_email
                if profile_phone:
                    user.mobile_number = profile_phone
                if profile_designation:
                    user.designation = profile_designation
                if profile_about:
                    user.about = profile_about
                if profile_username:
                    user.username = profile_username

                # Update profile image if uploaded
                profile_image = self.request.FILES.get('profile_image')
                if profile_image:
                    user.profile_image = profile_image
                
                # ✅ Update password ONLY if provided
                if password:
                    if password != confirm_password:
                        form.add_error(None, 'Password and confirm password do not match.')
                        return self.form_invalid(form)
                    user.set_password(password)
                    # Note: set_password doesn't automatically save
                    # We'll save below with all other changes
                
                # ✅ REMOVED: Manual last_login update
                # last_login should only be updated by Django's login() function
                # during actual user authentication
                
                # ✅ Save all user changes (including password if changed)
                user.save()
            
            messages.success(self.request, 'Company and company admin updated successfully.')
            return redirect(self.get_success_url())

    def form_invalid(self, form):
        context = self.get_context_data()
        context['form'] = form
        return self.render_to_response(context)
   
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
    



def get_states(request, country_id):
    states = State.objects.filter(country_id=country_id,is_active=True).order_by("name")
    data = list(states.values("id","name"))

    return JsonResponse(data, safe=False)


def get_cities(request, state_id):
    cities = City.objects.filter(state_id=state_id,is_active=True).order_by("name")
    data = list(cities.values("id","name"))

    return JsonResponse(data, safe=False)