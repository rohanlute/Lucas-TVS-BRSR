from django.views.generic import (ListView,TemplateView)
from django.contrib.auth.mixins import (LoginRequiredMixin)
from .models import Company
from apps.accounts.mixins import (SuperAdminRequiredMixin)


# -----------------------------------------------
# ============= Company Management - Admin =======================
# -----------------------------------------------
class CompanyListView(LoginRequiredMixin,SuperAdminRequiredMixin,ListView):

    model = Company

    template_name = ('companies/company_list.html')

    context_object_name = ('companies')

    login_url = ('accounts:login')

# ============= Company Management - Create =======================

class CompanyCreateView(LoginRequiredMixin,SuperAdminRequiredMixin,TemplateView):

    template_name = ('companies/company_create.html')

    login_url = ('accounts:login')


# ============= Company Management - View =======================
class CompanyDetailView(LoginRequiredMixin,SuperAdminRequiredMixin,TemplateView):

    template_name = ('companies/company_view.html')

    login_url = ('accounts:login')