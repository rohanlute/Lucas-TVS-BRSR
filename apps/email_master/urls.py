from django.urls import path
from .views import *

app_name = "email_master"

urlpatterns = [
    path('email_list/',EmailListView.as_view(),name='email_list'),
]