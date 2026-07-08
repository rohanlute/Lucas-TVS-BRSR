from django.contrib import admin

from .models import (
    EmissionScope,
    EmissionCategory,
    EmissionActivity,
    EmissionFactor,
    EmissionTransaction,
)


# =====================================================
# Emission Scope
# =====================================================

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


# =====================================================
# Emission Category
# =====================================================

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

    list_editable = (
        "display_order",
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


# =====================================================
# Emission Activity
# =====================================================

@admin.register(EmissionActivity)
class EmissionActivityAdmin(admin.ModelAdmin):

    list_display = (
        "code",
        "name",
        "category",
        "base_unit",
        "requires_emission_factor",
        "allow_manual_entry",
        "allow_excel_import",
        "is_active",
    )

    list_filter = (
        "category",
        "requires_emission_factor",
        "is_active",
    )

    list_editable = (
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


# =====================================================
# Emission Factor
# =====================================================

@admin.register(EmissionFactor)
class EmissionFactorAdmin(admin.ModelAdmin):

    list_display = (
        "activity",
        "unit",
        "emission_factor",
        "effective_from",
        "effective_to",
        "is_active",
    )

    list_filter = (
        "activity__category",
        "is_active",
    )

    search_fields = (
        "activity__name",
    )

    ordering = (
        "activity",
        "-effective_from",
    )


# =====================================================
# Emission Transaction
# =====================================================

@admin.register(EmissionTransaction)
class EmissionTransactionAdmin(admin.ModelAdmin):

    list_display = (
        "company",
        "plant",
        "financial_year",
        "financial_month",
        "activity",
        "quantity",
        "unit",
        "emission_factor",
        "total_emission",
        "created_by",
        "created_at",
    )

    list_filter = (
        "company",
        "plant",
        "financial_year",
        "financial_month",
        "activity__category",
    )

    search_fields = (
        "company__company_name",
        "plant__name",
        "activity__name",
        "remarks",
    )

    readonly_fields = (
        "emission_factor",
        "emission_factor_source",
        "total_emission",
        "created_at",
        "updated_at",
    )

    ordering = (
        "-financial_year",
        "financial_month",
        "plant",
    )

    fieldsets = (

        (
            "Transaction Details",
            {
                "fields": (
                    "company",
                    "plant",
                    "financial_year",
                    "financial_month",
                    "activity",
                    "unit",
                    "quantity",
                    "remarks",
                )
            },
        ),

        (
            "Emission Calculation",
            {
                "fields": (
                    "emission_factor_source",
                    "emission_factor",
                    "total_emission",
                )
            },
        ),

        (
            "Audit Information",
            {
                "classes": ("collapse",),
                "fields": (
                    "created_by",
                    "created_at",
                    "updated_at",
                ),
            },
        ),
    )