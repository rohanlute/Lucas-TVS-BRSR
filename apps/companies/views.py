from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from .models import Company
from apps.accounts.decorators import superadmin_required

@login_required(login_url='accounts:login')
@superadmin_required
def company_list(request):
    companies = Company.objects.all()
    context = {
        'companies': companies
    }
    return render(request,'companies/company_list.html',context)


@login_required(login_url='accounts:login')
@superadmin_required
def company_create(request):
    return render(request,'companies/company_create.html')

@login_required(login_url='accounts:login')
@superadmin_required
def company_view(request):
    return render(request,'companies/company_view.html')