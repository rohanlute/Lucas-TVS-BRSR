from django.urls import path
from . import views

app_name = 'goals'

urlpatterns = [
    path('', views.DashboardView.as_view(), name='dashboard'),
    path('add-goal/', views.AddGoalView.as_view(), name='add_goal'),
    path('delete-goal/<str:goal_id>/', views.DeleteGoalView.as_view(), name='delete_goal'),
    path('delete-topic/<str:topic>/', views.DeleteTopicView.as_view(), name='delete_topic'),
    path('goal/<str:material_topic>/', views.GoalDetailView.as_view(), name='goal_detail'),
    path('goal-config/<str:material_topic>/', views.GoalConfigUpdateView.as_view(), name='goal_config_update'),
    path('api/goal-metrics/<str:material_topic>/', views.GoalMetricsAPIView.as_view(), name='goal_metrics_api'),
    
    # Initiative URLs
    path('initiatives/', views.InitiativeListView.as_view(), name='initiative_list'),
    path('initiatives/create/', views.InitiativeCreateView.as_view(), name='initiative_create'),
    path('initiatives/delete/<int:initiative_id>/', views.InitiativeDeleteView.as_view(), name='initiative_delete'),
    path('initiatives/edit/<int:initiative_id>/', views.InitiativeEditView.as_view(), name='initiative_edit'),
    path('initiatives/detail/<str:material_topic>/', views.InitiativeDetailView.as_view(), name='initiative_detail'),
    path('initiative/delete/<int:initiative_id>/', views.InitiativeDeleteView.as_view(), name='initiative_delete'),
    path('delete-kpi-initiatives/', views.DeleteKpiInitiativesView.as_view(), name='delete_kpi_initiatives'),
    # API URLs
    path('api/get-metrics/', views.GetMetricsForGoalAPIView.as_view(), name='get_metrics_api'),
    path('clear-initiatives/', views.ClearInitiativesView.as_view(), name='clear_initiatives'),
]