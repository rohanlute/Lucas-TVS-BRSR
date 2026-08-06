# apps/goals/urls.py

from django.urls import path
from . import views

app_name = 'goals'

urlpatterns = [
    # Dashboard
    path('', views.DashboardView.as_view(), name='dashboard'),
    
    # Goal Management
    path('add-goal/', views.AddGoalView.as_view(), name='add_goal'),
    path('delete/<str:goal_id>/', views.DeleteGoalView.as_view(), name='delete_goal'),
    path('delete-topic/<str:topic>/', views.DeleteTopicView.as_view(), name='delete_topic'),
    
    # Goal Detail
    path('detail/<str:material_topic>/', views.GoalDetailView.as_view(), name='goal_detail'),
    
    # Goal Config
    path('config/update/<str:material_topic>/', views.GoalConfigUpdateView.as_view(), name='goal_config_update'),
    
    # ===== API ENDPOINTS =====
    # Get current KPI value
    path('api/kpi/current-value/', views.KPICurrentValueAPIView.as_view(), name='kpi_current_value'),
    
    # Get KPI configuration (plant-specific)
    path('api/kpi/config/', views.KPIConfigAPIView.as_view(), name='kpi_config'),
    
    # Get metrics for a goal
    path('api/goal-metrics/<str:material_topic>/', views.GoalMetricsAPIView.as_view(), name='goal_metrics'),
    
    # Initiatives
    path('initiatives/', views.InitiativeListView.as_view(), name='initiative_list'),
    path('initiatives/add/', views.InitiativeCreateView.as_view(), name='initiative_add'),
    path('initiatives/delete/<int:initiative_id>/', views.InitiativeDeleteView.as_view(), name='initiative_delete'),
    path('initiatives/clear/', views.ClearInitiativesView.as_view(), name='initiative_clear'),
    
    # Test
    path('test/', views.TestView.as_view(), name='test'),
]