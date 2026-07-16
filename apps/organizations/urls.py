from django.urls import path
from . import views
from .views import *

app_name = 'organizations'

urlpatterns = [
    
    # Plant URLs
    path('plants/', views.PlantListView.as_view(), name='plant_list'),
    path('plants/create/', views.PlantCreateView.as_view(), name='plant_create'),
    path('plants/<int:pk>/edit/', views.PlantUpdateView.as_view(), name='plant_update'),
    path('plants/<int:pk>/delete/', views.PlantDeleteView.as_view(), name='plant_delete'),
    path("financial-years/",FinancialYearListView.as_view(),name="financial_year_list"),
    path("financial-years/create/",FinancialYearCreateView.as_view(),name="financial_year_create"),
    path("financial-years/<int:pk>/edit/",FinancialYearUpdateView.as_view(),name="financial_year_update"),
    path('calendar/', views.CalendarWeekView.as_view(), name='calendar'),
    # Workflow Configuration URLs
    path('workflow-configurations/', views.WorkflowConfigurationTemplateListView.as_view(), name='workflow_configuration_template_list'),
    path('workflow-configurations/create/', views.WorkflowConfigurationTemplateEditorView.as_view(), name='workflow_configuration_template_create'),
    path('workflow-configurations/<int:pk>/edit/', views.WorkflowConfigurationTemplateEditorView.as_view(), name='workflow_configuration_template_edit'),
    path('workflow-configurations/<int:pk>/delete/', views.WorkflowConfigurationTemplateDeleteView.as_view(), name='workflow_configuration_template_delete'),
    path('workflow-tasks/<int:pk>/history/', views.WorkflowConfigurationTaskHistoryView.as_view(), name='workflow_configuration_task_history'),
]
