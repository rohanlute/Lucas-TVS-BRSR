from django.urls import path
from .views import *

app_name = 'accounts'

urlpatterns = [
    # -----------------------------------------------
    # ============= Login/Logout/ForgotPassword =======================
    # -----------------------------------------------
    path('',LoginView.as_view(),name='login'),
    path('logout/',LogoutView.as_view(),name='logout'),
    path('Forgot_pass/',ForgotPasswordView.as_view(),name='Forgot_pass'),
    path('reset-password/<uidb64>/<token>/', CustomPasswordResetConfirmView.as_view(), name='password_reset_confirm'),

    # -----------------------------------------------
    # ============= Dashboard =======================
    # -----------------------------------------------

    path('dashboard/',DashboardView.as_view(),name='dashboard'),

    # -----------------------------------------------
    # ============= User =======================
    # -----------------------------------------------

    path('user_list/',UserListView.as_view(),name='user_list'),

    path('user_create/',UserCreateView.as_view(),name='user_create'),

    path('user_edit/<int:pk>/',UserUpdateView.as_view(),name='user_edit'),

    path('user_view/<int:pk>/',UserDetailView.as_view(),name='user_view'),

    path('user_delete/<int:pk>/',UserDeleteView.as_view(),name='user_delete'),

    # -----------------------------------------------
    # ============= Role & Permission ===============
    # -----------------------------------------------

    path('role-list/', RoleListView.as_view(), name='role_list'),

    path('createrole/', RoleCreateView.as_view(), name='role_create'),

    path('editrole/<int:pk>/', RoleUpdateView.as_view(), name='role_edit'),

    path('createrole/<int:pk>/', RoleUpdateView.as_view(), name='role_edit_legacy'),

    # -----------------------------------------------
    # ============= Department =======================
    # -----------------------------------------------

    path('department_list/',DepartmentListView.as_view(),name='department_list'),

    path('department_create/',DepartmentCreateView.as_view(),name='department_create'),

    path('department_view/<int:pk>/',DepartmentDetailView.as_view(),name='department_view'),

    path('department_edit/<int:pk>/',DepartmentUpdateView.as_view(),name='department_edit'),

    path('department_delete/<int:pk>/',DepartmentDeleteView.as_view(),name='department_delete'),
]
