from django.urls import path

from .views import (
    LoginView,LogoutView,DashboardView,UserListView,
    UserCreateView,DepartmentListView,DepartmentCreateView,
)

app_name = 'accounts'

urlpatterns = [
    # -----------------------------------------------
    # ============= Login/Logout =======================
    # -----------------------------------------------
    path('',LoginView.as_view(),name='login'),

    path('logout/',LogoutView.as_view(),name='logout'),

    # -----------------------------------------------
    # ============= Dashboard =======================
    # -----------------------------------------------

    path('dashboard/',DashboardView.as_view(),name='dashboard'),

    # -----------------------------------------------
    # ============= User =======================
    # -----------------------------------------------

    path('user_list/',UserListView.as_view(),name='user_list'),

    path('user_create/',UserCreateView.as_view(),name='user_create'),

    # -----------------------------------------------
    # ============= Department =======================
    # -----------------------------------------------

    path('department_list/',DepartmentListView.as_view(),name='department_list'),

    path('department_create/',DepartmentCreateView.as_view(),name='department_create'),
]