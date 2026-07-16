from django.contrib import admin
from .models import *
from .models import FinancialMonth


@admin.register(Plant)
class PlantAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'city', 'state', 'contact_person', 'is_active', 'created_at']
    list_filter = ['is_active', 'state', 'city']
    search_fields = ['name', 'code', 'city', 'contact_person']
    ordering = ['name']

@admin.register(FinancialMonth)
class FinancialMonthAdmin(admin.ModelAdmin):

    list_display = (
        "month_number",
        "month_code",
        "month_name",
        "quarter",
        "half_year",
        "display_order",
        "is_active",
    )

    list_editable = (
        "display_order",
        "is_active",
    )

    ordering = (
        "display_order",
    )

    search_fields = (
        "month_name",
        "month_code",
    )


class WorkflowConfigurationStageInline(admin.TabularInline):
    model = ApprovalConfigurationStage
    extra = 0
    fields = (
        "level",
        "label",
        "stage_type",
        "role",
        "can_approve",
        "can_reject",
        "can_reassign",
        "can_escalate",
        "due_days",
        "escalation_role",
    )


@admin.register(ApprovalConfigurationTemplate)
class WorkflowConfigurationTemplateAdmin(admin.ModelAdmin):
    list_display = ("name", "company", "framework", "is_active", "stage_count", "created_at")
    list_filter = ("is_active", "framework", "company")
    search_fields = ("name", "company__company_name")
    inlines = [WorkflowConfigurationStageInline]
    ordering = ("company__company_name", "framework", "name")

    def stage_count(self, obj):
        return obj.stages.count()


@admin.register(ApprovalConfigurationStage)
class WorkflowConfigurationStageAdmin(admin.ModelAdmin):
    list_display = ("template", "level", "label", "role", "stage_type", "can_approve", "can_reject")
    list_filter = ("stage_type", "can_approve", "can_reject", "can_reassign", "can_escalate")
    search_fields = ("template__name", "label", "role__role_name")
    ordering = ("template", "level")


@admin.register(ApprovalConfigurationTask)
class WorkflowConfigurationTaskAdmin(admin.ModelAdmin):
    list_display = ("id", "template", "current_stage", "current_assignee", "is_completed", "is_returned", "created_at")
    list_filter = ("is_completed", "is_returned", "template__company", "template__framework")
    search_fields = ("template__name",)
    readonly_fields = ("created_at", "updated_at")


@admin.register(ApprovalConfigurationTaskLog)
class WorkflowConfigurationTaskLogAdmin(admin.ModelAdmin):
    list_display = ("task", "action", "from_stage", "to_stage", "actor", "created_at")
    list_filter = ("action",)
    search_fields = ("task__template__name", "remark")
    readonly_fields = ("created_at",)


# Backward-compatible aliases.
ApprovalConfigurationStageInline = WorkflowConfigurationStageInline
ApprovalConfigurationTemplateAdmin = WorkflowConfigurationTemplateAdmin
ApprovalConfigurationStageAdmin = WorkflowConfigurationStageAdmin
ApprovalConfigurationTaskAdmin = WorkflowConfigurationTaskAdmin
ApprovalConfigurationTaskLogAdmin = WorkflowConfigurationTaskLogAdmin
