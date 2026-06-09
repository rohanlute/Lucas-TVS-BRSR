from django.urls import path
from .views import *

app_name = 'accounts'

urlpatterns = [
    # Login/Logout
    path('', login_view, name='login'),
    path('logout/', logout_view, name='logout'),

    # Dashboard "HOME"
    path('dashboard/', dashboard, name='dashboard'),

    # User Management
    path('user_list/', user_list, name='user_list'),
    path('user_create/', user_create, name='user_create'),

    # Department
    path('department_list/', department_list, name='department_list'),
    path('department_create/', department_create, name='department_create'),
]