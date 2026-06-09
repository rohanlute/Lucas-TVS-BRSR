from django.contrib import admin
from .models import Company


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):

    list_display = (
        'company_code',
        'company_name',
        'contact_person',
        'email',
        'is_active'
    )

    search_fields = (
        'company_code',
        'company_name',
        'email'
    )