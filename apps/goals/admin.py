# apps/goals/admin.py
from django.contrib import admin
from .models import MaterialTopic, Goal, KPI, KPIPlantTarget


@admin.register(MaterialTopic)
class MaterialTopicAdmin(admin.ModelAdmin):
    list_display = ['name', 'is_active', 'created_by', 'created_at']
    search_fields = ['name']
    list_filter = ['is_active']
    readonly_fields = ['created_at', 'updated_at', 'created_by', 'updated_by']
    
    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(Goal)
class GoalAdmin(admin.ModelAdmin):
    list_display = ['name', 'material_topic', 'is_active', 'created_by']
    search_fields = ['name', 'material_topic__name']
    list_filter = ['material_topic', 'is_active']
    readonly_fields = ['created_at', 'updated_at', 'created_by', 'updated_by']
    
    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(KPI)
class KPIAdmin(admin.ModelAdmin):
    list_display = ['name', 'goal', 'unit', 'baseline_value', 'target_value', 'is_active']
    search_fields = ['name', 'goal__name']
    list_filter = ['goal__material_topic', 'is_active']
    readonly_fields = ['created_at', 'updated_at', 'created_by', 'updated_by']
    
    fieldsets = (
        ('KPI Information', {
            'fields': ('goal', 'name', 'unit', 'is_active')
        }),
        ('Baseline', {
            'fields': ('baseline_year', 'baseline_value')
        }),
        ('Target', {
            'fields': ('target_year', 'target_reduction', 'target_value')
        }),
        ('Emission Data Mapping', {
            'fields': ('category_keyword', 'activity_keyword', 'source_keyword'),
            'help_text': 'Keywords to match category, activity.name, or source.source_name in EmissionTransaction'
        }),
        ('Audit', {
            'fields': ('created_at', 'updated_at', 'created_by', 'updated_by'),
            'classes': ('collapse',)
        }),
    )
    
    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(KPIPlantTarget)
class KPIPlantTargetAdmin(admin.ModelAdmin):
    list_display = ['kpi', 'plant', 'baseline_value', 'target_value', 'baseline_year', 'target_year']
    search_fields = ['kpi__name', 'plant__name']
    list_filter = ['plant', 'kpi__goal__material_topic']
    readonly_fields = ['created_at', 'updated_at', 'created_by', 'updated_by']

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)