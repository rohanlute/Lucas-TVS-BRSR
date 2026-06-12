from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.views import View
from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
from .mixins import SuperAdminRequiredMixin
from django.urls import reverse_lazy
from django.views.generic import (ListView,CreateView,UpdateView,DetailView)
from .forms import UserCreateForm
from .models import User
from apps.accounts.models import Role
from apps.companies.models import Company


# -----------------------------------------------
# ============= LOGIN ===========================
# -----------------------------------------------

class LoginView(View):

    template_name = 'base/login.html'

    def get(self, request):
        return render(request,self.template_name)

    def post(self, request):

        username = request.POST.get('username')
        password = request.POST.get('password')

        user = authenticate(request,username=username,password=password)
        if user:
            login(request,user)
            user.is_online = True
            user.save()
            return redirect('accounts:dashboard')

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

class UserListView(LoginRequiredMixin,SuperAdminRequiredMixin,ListView):

    model = User

    template_name = ('accounts/user_management/user_list.html')

    context_object_name = 'users'

    def get_queryset(self):

        return User.objects.select_related('role','company').filter(role__role_code='SUPERADMIN').order_by('-id')

# ============= USER LIST =======================

class UserCreateView(LoginRequiredMixin,SuperAdminRequiredMixin,CreateView):

    model = User

    form_class = UserCreateForm

    template_name = ('accounts/user_management/user_create.html')

    success_url = reverse_lazy('accounts:user_list')

    

    def form_valid(self, form):

        user = form.save(commit=False)

        if self.request.FILES.get('profile_image'):
            user.profile_image = self.request.FILES.get('profile_image')

        user.set_password(form.cleaned_data['password'])

        role = Role.objects.get(role_code='SUPERADMIN')

        company = Company.objects.get(company_code='PROTEGK')

        user.role = role

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
    

class UserUpdateView(LoginRequiredMixin,SuperAdminRequiredMixin,UpdateView):

    model = User

    form_class = UserCreateForm

    template_name = ('accounts/user_management/user_create.html')

    success_url = reverse_lazy('accounts:user_list')

    def get_context_data(self, **kwargs):

        context = super().get_context_data(**kwargs)

        context['page_title'] = 'Edit User'

        return context



class UserDetailView(LoginRequiredMixin,SuperAdminRequiredMixin,DetailView):

    model = User

    template_name = ('accounts/user_management/user_view.html')

    context_object_name = 'user_obj'
# -----------------------------------------------
# ============= Department =======================
# -----------------------------------------------

class DepartmentListView(LoginRequiredMixin,SuperAdminRequiredMixin,TemplateView):

    login_url = 'accounts:login'

    template_name = ('accounts/department/department_list.html')

# ================= Department Create ==============
class DepartmentCreateView(LoginRequiredMixin,SuperAdminRequiredMixin,TemplateView):

    login_url = 'accounts:login'

    template_name = ('accounts/department/department_create.html')