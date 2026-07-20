from django.urls import path
from .views import (
    EmissionsDashboardView, 
    EmissionsDashboardDataView,
    ScopeDashboardView,
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
    CategoryActivitiesView,
    ActivityFactorView,
    SaveEmissionTransactionsView,
    LoadEmissionTransactionsView,
    ScopeCategoriesView,
)

app_name = "emission"

urlpatterns = [
    # ===== DASHBOARD =====
    path("", EmissionsDashboardView.as_view(), name="dashboard"),
    path("api/data/", EmissionsDashboardDataView.as_view(), name="dashboard-data"),

    #====== SCOPE =======
    path("scope_dataentry/", ScopeDashboardView.as_view(), name="scope_dataentry"),
    path("api/category-activities/",CategoryActivitiesView.as_view(),name="category-activities"),
    path("api/activity-factor/",ActivityFactorView.as_view(),name="activity-factor"),
    path("api/save-transactions/",SaveEmissionTransactionsView.as_view(),name="save-transactions"),
    path("api/load-transactions/",LoadEmissionTransactionsView.as_view(),name="load-transactions"),
    path("api/scope-categories/",ScopeCategoriesView.as_view(),name="scope_categories"),
    
    
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
