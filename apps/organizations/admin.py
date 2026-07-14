from django.contrib import admin
from .models import *
from .models import FinancialMonth


class SubLocationInline(admin.TabularInline):
    model = SubLocation
    extra = 1
    fields = ['name', 'code', 'description', 'is_active']


@admin.register(Plant)
class PlantAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'city', 'state', 'contact_person', 'is_active', 'created_at']
    list_filter = ['is_active', 'state', 'city']
    search_fields = ['name', 'code', 'city', 'contact_person']
    ordering = ['name']


@admin.register(Zone)
class ZoneAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'plant', 'is_active', 'created_at']
    list_filter = ['is_active', 'plant']
    search_fields = ['name', 'code', 'plant__name']
    ordering = ['plant', 'name']


@admin.register(Location)
class LocationAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'zone', 'get_plant', 'sublocation_count', 'is_active', 'created_at']
    list_filter = ['is_active', 'zone__plant', 'zone']
    search_fields = ['name', 'code', 'zone__name', 'zone__plant__name']
    ordering = ['zone__plant', 'zone', 'name']
    inlines = [SubLocationInline]  # ADD THIS LINE
    
    def get_plant(self, obj):
        return obj.zone.plant.name
    get_plant.short_description = 'Plant'
    get_plant.admin_order_field = 'zone__plant__name'
    
    def sublocation_count(self, obj):
        return obj.sublocations.count()
    sublocation_count.short_description = 'Sub-Locations'


@admin.register(SubLocation)
class SubLocationAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'location', 'get_zone', 'get_plant', 'is_active', 'created_at']
    list_filter = ['is_active', 'location__zone__plant', 'location__zone']
    search_fields = ['name', 'code', 'location__name', 'location__zone__name', 'location__zone__plant__name']
    ordering = ['location__zone__plant', 'location__zone', 'location', 'name']
    
    def get_zone(self, obj):
        return obj.location.zone.name
    get_zone.short_description = 'Zone'
    get_zone.admin_order_field = 'location__zone__name'
    
    def get_plant(self, obj):
        return obj.location.zone.plant.name
    get_plant.short_description = 'Plant'
    get_plant.admin_order_field = 'location__zone__plant__name'



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
