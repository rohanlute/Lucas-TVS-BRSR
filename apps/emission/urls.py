from django.urls import path
from .views_excel import download_scope_template, upload_scope_template
from .api_views import (ApproveAssignmentView, RejectAssignmentView, CoordinatorApproveAssignmentView,
    CoordinatorRejectAssignmentView,SaveEmissionScheduleAPIView,EmissionScheduleListAPIView,
    UpdateEmissionScheduleAPIView,ToggleEmissionScheduleAPIView,DeleteEmissionScheduleAPIView,
    ToggleScheduleStatusAPIView,ScheduleHistoryAPIView)
from .views import (EmissionAssignmentDashboardView,EmissionsDashboardView,EmissionsDashboardDataView,
    PlantUsersAPIView,SaveEmissionAssignmentAPIView,ScopeDashboardView,ESGDisclosureView,
    CategoryActivitiesView,ActivityFactorView,SaveEmissionTransactionsView,LoadEmissionTransactionsView,
    ScopeCategoriesView,EmissionAssignmentDetailView,SubmitAssignmentView,CheckAssignedSourcesAPIView,ESGDisclosureDataAPIView,
    EmissionSchedulerDashboardView)

app_name = "emission"

urlpatterns = [
    # ===== Analytical DASHBOARD =====
    path("", EmissionsDashboardView.as_view(), name="dashboard"),
    path("api/data/", EmissionsDashboardDataView.as_view(), name="dashboard-data"),

    #====== SCOPE =======
    path("scope_dataentry/", ScopeDashboardView.as_view(), name="scope_dataentry"),
    path("api/category-activities/",CategoryActivitiesView.as_view(),name="category-activities"),
    path("api/activity-factor/",ActivityFactorView.as_view(),name="activity-factor"),
    path("api/save-transactions/",SaveEmissionTransactionsView.as_view(),name="save-transactions"),
    path("api/load-transactions/",LoadEmissionTransactionsView.as_view(),name="load-transactions"),
    path("api/scope-categories/",ScopeCategoriesView.as_view(),name="scope_categories"),
    path("api/plant-users/",PlantUsersAPIView.as_view(),name="plant_users"),
    
    
    #=====report====
    path('report/', ESGDisclosureView.as_view(), name='esg-disclosure'),
    path('api/esg-data/', ESGDisclosureDataAPIView.as_view(), name='esg-data-api'),

    #====== Correct Working Use ASSIGNMENT=====
    path("assignments/",EmissionAssignmentDashboardView.as_view(),name="assignment_dashboard"),
    path("api/assignment/save/",SaveEmissionAssignmentAPIView.as_view(),name="save-emission-assignment"),
    path("api/submit-assignment/",SubmitAssignmentView.as_view(),name="submit_assignment"),
    path("assignments/<int:assignment_id>/",EmissionAssignmentDetailView.as_view(),name="assignment_detail"),
    # Reviwer Approval
    path("api/approve-assignment/",ApproveAssignmentView.as_view(),name="approve_assignment"),
    # Coordinator 
    path("api/coordinator-approve-assignment/",CoordinatorApproveAssignmentView.as_view(),name="coordinator_approve_assignment"),
    path("api/coordinator-reject/",CoordinatorRejectAssignmentView.as_view(),name="coordinator_reject"),
    path("api/reject-assignment/",RejectAssignmentView.as_view(),name="reject_assignment"),
    path("api/scope-template/download/", download_scope_template,name="download_scope_template"),
    path("api/scope-template/upload/", upload_scope_template,name="upload_scope_template"),
    path("api/assignment/check-assigned-sources/",CheckAssignedSourcesAPIView.as_view(),name="check_assigned_sources"),
    path("api/schedules/save/",SaveEmissionScheduleAPIView.as_view(),name="save_schedule"),
    path("api/schedules/list/",EmissionScheduleListAPIView.as_view(),name="schedule_list"),
    path("api/schedules/<int:schedule_id>/update/",UpdateEmissionScheduleAPIView.as_view(),name="update_schedule"),
    path("api/schedules/<int:schedule_id>/toggle/",ToggleEmissionScheduleAPIView.as_view(),name="toggle_schedule"),
    path("api/schedules/<int:schedule_id>/delete/",DeleteEmissionScheduleAPIView.as_view(),name="delete_schedule"),

    path("scheduler/dashboard/",EmissionSchedulerDashboardView.as_view(),name="scheduler_dashboard"),
    path("api/scheduler/toggle-status/",ToggleScheduleStatusAPIView.as_view(),name="toggle_schedule_status"),
    path("api/scheduler/<int:schedule_id>/history/",ScheduleHistoryAPIView.as_view(),name="schedule_history"),
]
