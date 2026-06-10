from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.views import View
from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
from .mixins import SuperAdminRequiredMixin

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
            return redirect('accounts:dashboard')

        messages.error(request,'Invalid Username or Password')

        return render(request,self.template_name)


# -----------------------------------------------
# ============= LOGOUT ==========================
# -----------------------------------------------

class LogoutView(View):

    def get(self, request):

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

class UserListView(LoginRequiredMixin,SuperAdminRequiredMixin,TemplateView):

    login_url = 'accounts:login'

    template_name = ('accounts/user_management/user_list.html')

# ============= USER LIST =======================

class UserCreateView(LoginRequiredMixin,SuperAdminRequiredMixin,TemplateView):

    login_url = 'accounts:login'

    template_name = ('accounts/user_management/user_create.html')


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