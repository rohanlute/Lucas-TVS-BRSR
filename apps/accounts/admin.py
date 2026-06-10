from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import User, Role


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

    fieldsets = UserAdmin.fieldsets + (
        (
            'Additional Information',
            {
                'fields': (
                    'employee_code',
                    'role',
                    'company',
                    'mobile_number',
                    'profile_image',
                    'is_company_user'
                )
            }
        ),
    )