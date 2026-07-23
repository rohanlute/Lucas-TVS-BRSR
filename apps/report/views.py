# apps/report/views.py
"""
Views behind report_generate.html — the report dashboard page with the
year filter, report cards (PDF/Excel download), and the recent reports table.
"""

import json
from datetime import datetime
import logging

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.urls import reverse
from django.utils import timezone
from .views_brsr import BRSRReportPDFDownloadView, BRSRReportExcelDownloadView
from django.views import View
from django.views.generic import TemplateView

from .brsr_report_data import get_brsr_report_data

logger = logging.getLogger(__name__)

# Global in-memory storage for reports (for debugging)
# This will persist across requests but will reset when server restarts
REPORT_STORAGE = {}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _reporting_years():
    """
    Years shown in the "Reporting Year" dropdown.
    """
    from apps.organizations.models import FinancialYear

    years = list(FinancialYear.objects.order_by("-start_date").values_list("financial_year", flat=True))
    return years or ["2024-2025"]


def _brsr_report_stats(financial_year):
    """
    Quick counts to show on the BRSR report card: total questions,
    how many have an answer, and progress %.
    """
    report_sections = get_brsr_report_data(financial_year=financial_year)

    total = 0
    answered = 0
    for block in report_sections:
        if block["is_principle_section"]:
            for p_block in block["principle_blocks"]:
                for row in p_block["rows"]:
                    total += 1
                    if row["answer_value"]:
                        answered += 1
        else:
            for sub in block["sub_sections"]:
                for row in sub["rows"]:
                    total += 1
                    if row["answer_value"]:
                        answered += 1

    progress = round((answered / total * 100), 1) if total else 0
    return total, answered, progress


def _available_reports(selected_year):
    """
    Cards shown in the "Available Reports" grid. Add your other report
    types here (financial, compliance, etc.) alongside the BRSR entry.
    """
    fy_label = selected_year
    total_q, answered_q, progress = _brsr_report_stats(selected_year)

    reports = [
        {
            "title": "BRSR Report",
            "description": (
                "Business Responsibility & Sustainability Report, generated live "
                "from your BRSR questionnaire."
            ),
            "accent": "green",
            "fy": selected_year,
            "stats": [
                {"value": total_q, "label": "Questions", "color": ""},
                {"value": answered_q, "label": "Answered", "color": "blue"},
                {"value": f"{progress}%", "label": "Complete", "color": "green"},
            ],
            "pdf_url": f"{reverse('report:brsr_report_pdf')}?financial_year={fy_label}",
            "excel_url": f"{reverse('report:brsr_report_excel')}?financial_year={fy_label}",
            "view_url": f"{reverse('report:brsr_report_preview')}?financial_year={fy_label}",
        },
        # Add other report types (financial statements, compliance report, etc.) here.
    ]
    return reports


def _get_recent_reports_from_storage(request, selected_year):
    """
    Get recent reports from global storage.
    """
    global REPORT_STORAGE
    
    storage_key = f"{request.user.id}_{selected_year}"
    reports = REPORT_STORAGE.get(storage_key, [])
    
    logger.info(f"Retrieved {len(reports)} reports from storage for {selected_year}")
    return reports


def _add_report_to_storage(request, selected_year, report_data):
    """
    Add a generated report to global storage.
    """
    global REPORT_STORAGE
    
    storage_key = f"{request.user.id}_{selected_year}"
    reports = REPORT_STORAGE.get(storage_key, [])
    
    if not isinstance(reports, list):
        reports = []
    
    # Add to beginning of list (most recent first)
    reports.insert(0, report_data)
    
    # Keep only last 50 reports
    reports = reports[:50]
    
    # Save to global storage
    REPORT_STORAGE[storage_key] = reports
    
    logger.info(f"Added report to storage. Total reports for {selected_year}: {len(reports)}")
    logger.info(f"Report data: {report_data}")
    
    return reports


def _recent_reports(request, selected_year):
    """
    Rows for the "Recent Reports" table.
    Uses global storage to track generated reports.
    """
    return _get_recent_reports_from_storage(request, selected_year)


# ---------------------------------------------------------------------------
# Views
# ---------------------------------------------------------------------------

class ReportGenerationView(LoginRequiredMixin, TemplateView):
    """Renders report_generate.html: year filter, report cards, recent reports table."""

    login_url = "accounts:login"
    template_name = "report/report_generate.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        reporting_years = _reporting_years()
        selected_year = self.request.GET.get("reporting_year") or (
            reporting_years[0] if reporting_years else "2024-25"
        )

        recent_reports = _recent_reports(self.request, selected_year)
        completed_count = sum(1 for r in recent_reports if r.get("status_raw") == "completed")
        processing_count = sum(1 for r in recent_reports if r.get("status_raw") == "processing")

        context.update({
            "active_fy": reporting_years[0] if reporting_years else "2024-25",
            "reporting_years": reporting_years,
            "selected_year": selected_year,
            "available_reports": _available_reports(selected_year),
            "recent_reports": recent_reports,
            "total_reports_count": len(recent_reports),
            "completed_count": completed_count,
            "processing_count": processing_count,
        })
        
        # Debug: Log the reports being passed to template
        logger.info(f"Template context - recent_reports count: {len(recent_reports)}")
        
        return context


class ReportGenerateView(LoginRequiredMixin, View):
    """
    Handles the "Generate All" button's AJAX POST.
    Generates reports and stores them in global storage.
    """

    login_url = "accounts:login"

    def post(self, request, *args, **kwargs):
        reporting_year = request.POST.get("reporting_year")

        if not reporting_year:
            return JsonResponse(
                {"status": "error", "message": "Please select a reporting year."}, status=400
            )

        try:
            logger.info(f"Generating reports for year: {reporting_year}")
            logger.info(f"User ID: {request.user.id}")
            
            # Generate BRSR Report
            brsr_report = {
                "name": f"BRSR Report - FY {reporting_year}",
                "accent": "green",
                "type": "BRSR",
                "year": reporting_year,
                "generated_on": timezone.now().strftime("%Y-%m-%d %H:%M"),
                "status": "Completed",
                "status_raw": "completed",
                "pdf_url": f"{reverse('report:brsr_report_pdf')}?financial_year={reporting_year}",
                "excel_url": f"{reverse('report:brsr_report_excel')}?financial_year={reporting_year}",
                "detail_url": f"{reverse('report:report_detail')}?year={reporting_year}&type=brsr",
            }
            
            # Generate GHG Report (static)
            ghg_report = {
                "name": f"GHG Report - FY {reporting_year}",
                "accent": "purple",
                "type": "GHG",
                "year": reporting_year,
                "generated_on": timezone.now().strftime("%Y-%m-%d %H:%M"),
                "status": "Completed",
                "status_raw": "completed",
                "pdf_url": "#",
                "excel_url": "#",
                "detail_url": f"{reverse('report:report_detail')}?year={reporting_year}&type=ghg",
            }
            
            # Store both reports in global storage
            _add_report_to_storage(request, reporting_year, brsr_report)
            _add_report_to_storage(request, reporting_year, ghg_report)
            
            # Verify reports were saved
            verify_reports = _get_recent_reports_from_storage(request, reporting_year)
            logger.info(f"After saving, found {len(verify_reports)} reports in storage")
            
            # Also log what's in storage globally
            global REPORT_STORAGE
            logger.info(f"All storage keys: {list(REPORT_STORAGE.keys())}")

            return JsonResponse({
                "status": "success",
                "message": f"Reports for FY {reporting_year} have been generated successfully.",
                "report_count": len(verify_reports),
                "reports_preview": [r["name"] for r in verify_reports[:5]],  # Send names back for verification
            })
            
        except Exception as e:
            logger.error(f"Error generating reports: {str(e)}")
            return JsonResponse({
                "status": "error",
                "message": f"Error generating reports: {str(e)}",
            }, status=500)


class ReportDetailView(LoginRequiredMixin, TemplateView):
    """
    Detail page for a single generated report.
    """

    login_url = "accounts:login"
    template_name = "report/report_detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        report_type = self.request.GET.get("type")
        year = self.request.GET.get("year")
        
        # Try to find the report in storage
        if year and report_type:
            reports = _get_recent_reports_from_storage(self.request, year)
            for report in reports:
                if report.get("type", "").lower() == report_type.lower():
                    context["report"] = report
                    break
        
        context.update({
            "pk": kwargs.get("pk"),
            "report_type": report_type,
            "year": year,
        })
        return context


class ReportDownloadView(LoginRequiredMixin, View):
    """
    Generic download endpoint keyed by report_type + file_format, e.g.:
        /report/download/brsr/pdf/
        /report/download/brsr/excel/
    """

    login_url = "accounts:login"

    def get(self, request, report_type, file_format, *args, **kwargs):
        if report_type == "brsr":
            if file_format == "pdf":
                return BRSRReportPDFDownloadView.as_view()(request)
            if file_format in ("excel", "xlsx"):
                return BRSRReportExcelDownloadView.as_view()(request)
            return JsonResponse({"detail": f"Unsupported format '{file_format}' for BRSR."}, status=400)

        return JsonResponse({"detail": f"Unknown report_type '{report_type}'."}, status=404)


class ReportDataAPIView(LoginRequiredMixin, View):
    """
    JSON endpoint for populating the dashboard via AJAX.
    """

    login_url = "accounts:login"

    def get(self, request, *args, **kwargs):
        selected_year = request.GET.get("reporting_year") or (
            _reporting_years()[0] if _reporting_years() else "2024-25"
        )
        
        # Get fresh reports data
        reports = _recent_reports(request, selected_year)
        
        return JsonResponse({
            "selected_year": selected_year,
            "reporting_years": _reporting_years(),
            "available_reports": _available_reports(selected_year),
            "recent_reports": reports,
            "total_reports_count": len(reports),
            "completed_count": sum(1 for r in reports if r.get("status_raw") == "completed"),
            "processing_count": sum(1 for r in reports if r.get("status_raw") == "processing"),
        })

# Import placed at the bottom to avoid a circular import at module load time
  # noqa: E402