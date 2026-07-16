# apps/goals/urls.py

from django.urls import path
from . import views

app_name = 'goals'

urlpatterns = [
    path('', views.DashboardView.as_view(), name='dashboard'),
    path('add-goal/', views.AddGoalView.as_view(), name='add_goal'),
    path('delete-goal/<str:goal_id>/', views.DeleteGoalView.as_view(), name='delete_goal'),
    path('delete-topic/<str:topic>/', views.DeleteTopicView.as_view(), name='delete_topic'),
    # Updated URL with optional metric parameter
    path('goal-detail/<str:material_topic>/', views.GoalDetailView.as_view(), name='goal_detail'),
    path('goal-detail/<str:material_topic>/<str:metric_name>/', views.GoalDetailView.as_view(), name='goal_detail_metric'),
    path('goal-detail/<str:material_topic>/update/', views.GoalConfigUpdateView.as_view(), name='goal_config_update'),
    path('api/metrics/<str:material_topic>/', views.GoalMetricsAPIView.as_view(), name='goal_metrics_api'),
]