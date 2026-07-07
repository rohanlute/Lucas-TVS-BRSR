from django.contrib import admin
from .models import EmissionScope, EmissionCategory, EmissionActivity

@admin.register(EmissionScope)
class EmissionScopeAdmin(admin.ModelAdmin):
    list_display = (
        "code",
        "name",
        "display_order",
        "is_active",
    )

    list_editable = (
        "display_order",
        "is_active",
    )

    search_fields = (
        "code",
        "name",
    )

    ordering = (
        "display_order",
    )


@admin.register(EmissionCategory)
class EmissionCategoryAdmin(admin.ModelAdmin):

    list_display = (
        "code",
        "name",
        "scope",
        "display_order",
        "is_active",
    )

    list_filter = (
        "scope",
        "is_active",
    )

    search_fields = (
        "code",
        "name",
    )

    ordering = (
        "scope",
        "display_order",
    )



@admin.register(EmissionActivity)
class EmissionActivityAdmin(admin.ModelAdmin):

    list_display = (
        "code",
        "name",
        "category",
        "default_unit",
        "is_active",
    )

    list_filter = (
        "category",
        "is_active",
    )

    search_fields = (
        "code",
        "name",
    )

    ordering = (
        "category",
        "display_order",
    )