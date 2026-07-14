from django.urls import path
from .views import (
    EmissionsDashboardView, 
    EmissionsDashboardDataView,
    TaskListView,
    TaskFilterView,
    TaskToggleView,
    TaskExportView,
    AdministratorAssignmentsView,
    CreateAssignmentView,
    GetDepartmentsByPlantView,
    CreateAssignmentSubmitView,
    ESGDisclosureView,
    EmissionTransactionListView,
    EmissionTransactionDeleteView,
    EmissionTransactionUpdateView,
    EmissionTransactionCreateView,
)

app_name = "emission"

urlpatterns = [
    # ===== DASHBOARD =====
    path("", EmissionsDashboardView.as_view(), name="dashboard"),
    path("api/data/", EmissionsDashboardDataView.as_view(), name="dashboard-data"),
    
    # ===== TASK LIST =====
    path("tasks/", TaskListView.as_view(), name="task-list"),
    path("api/tasks/filter/", TaskFilterView.as_view(), name="task-filter"),
    path("api/tasks/toggle/", TaskToggleView.as_view(), name="task-toggle"),
    path("tasks/export/", TaskExportView.as_view(), name="task-export"),
    
    #======ASSIGNMENT=====
    path("administrator/", AdministratorAssignmentsView.as_view(), name="administrator-assignments"),
    path("administrator/create/", CreateAssignmentView.as_view(), name="create-assignment"),
    path("api/departments/", GetDepartmentsByPlantView.as_view(), name="get-departments"),
    path("api/assignment/create/", CreateAssignmentSubmitView.as_view(), name="create-assignment-submit"),
    
    #=====report====
    path("esg/", ESGDisclosureView.as_view(), name="esg-disclosure"),
    
    
    path("transactions/",EmissionTransactionListView.as_view(),name="transaction_list",),
    path("transactions/create/",EmissionTransactionCreateView.as_view(),name="transaction_create",),
    path("transactions/<int:pk>/edit/",EmissionTransactionUpdateView.as_view(),name="transaction_update",),
    path("transactions/<int:pk>/delete/",EmissionTransactionDeleteView.as_view(),name="transaction_delete",),
]
