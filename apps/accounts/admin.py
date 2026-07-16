from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import User, Role, Department


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):

    list_display = (
        'name',
        'code',
        'is_active',
        'created_at',
        'updated_at'
    )
    list_filter = ('is_active', 'created_at')
    search_fields = ('name', 'code', 'description')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):

    list_display = (
        'role_code',
        'role_name',
        'is_active'
    )


@admin.register(User)
class CustomUserAdmin(UserAdmin):

    list_display = (
        'username',
        'email',
        'role',
        'company',
        'is_active'
    )

    filter_horizontal = (
        'assigned_plants',
    )

    fieldsets = UserAdmin.fieldsets + (
        (
            'Additional Information',
            {
                'fields': (
                    'employee_code',
                    'full_name',
                    'role',
                    'company',
                    'mobile_number',
                    'designation',
                    'about',
                    'profile_image',
                    'is_company_user',
                    'assigned_plants',
                )
            }
        ),
    )