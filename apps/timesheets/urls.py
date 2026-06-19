from django.urls import path
from .views import *

app_name = "timesheets"

urlpatterns = [
    path('timesheet_list/',TimeSheetListView.as_view(),name='timesheet_list'),
]