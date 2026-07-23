# report_app/urls.py
from django.urls import path
from . import views
from .views_brsr import (
    BRSRReportPreviewView,
    BRSRReportPDFDownloadView,
    BRSRReportExcelDownloadView,
)

app_name = 'report'

urlpatterns = [
    # Report Generation Dashboard
    path('', views.ReportGenerationView.as_view(), name='generate'),
    
    # Generate Action
    path('generate/', views.ReportGenerateView.as_view(), name='generate_action'),
    
    # Report Detail
    path('detail/<int:pk>/', views.ReportDetailView.as_view(), name='report_detail'),
    path('detail/', views.ReportDetailView.as_view(), name='report_detail'),
    
    # Download Reports
    path('download/<str:report_type>/<str:file_format>/', views.ReportDownloadView.as_view(), name='download'),
    
    # API
    path('api/data/', views.ReportDataAPIView.as_view(), name='report_data_api'),
    
    # BRSR
    path("brsr/", BRSRReportPreviewView.as_view(), name="brsr_report_preview"),
    path("brsr/download/pdf/", BRSRReportPDFDownloadView.as_view(), name="brsr_report_pdf"),
    path("brsr/download/excel/", BRSRReportExcelDownloadView.as_view(), name="brsr_report_excel"),
]