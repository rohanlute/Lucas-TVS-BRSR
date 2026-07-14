from django.urls import path
from . import views

app_name = "goals"

urlpatterns = [
    path("", views.goal_dashboard, name="dashboard"),
]