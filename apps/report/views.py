# apps/report/views.py
"""
Views behind report_generate.html — the plant + year filters, report cards
(PDF/Excel download), and the recent reports table.
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


def _plants():
    """
    Plants shown in the "Plant" dropdown.
    """
    from apps.organizations.models import Plant

    return list(Plant.objects.filter(is_active=True).order_by("name"))


def _selected_plant_id(request, plants):
    """
    Resolves the active plant_id from GET or POST, falling back to the
    first available plant (mirrors how selected_year falls back to
    reporting_years[0]).
    """
    plant_id = request.GET.get("plant_id") or request.POST.get("plant_id")
    if plant_id:
        return plant_id
    return str(plants[0].id) if plants else None


def _brsr_report_stats(financial_year, plant_id=None):
    """
    Quick counts to show on the BRSR report card: total questions,
    how many have an answer, and progress %.
    """
    report_sections = get_brsr_report_data(financial_year=financial_year, plant_id=plant_id)

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


def _available_reports(selected_year, plant_id=None):
    """
    Returns the BRSR report card data.
    """
    fy_label = selected_year
    total_q, answered_q, progress = _brsr_report_stats(selected_year, plant_id)

    plant_qs = f"&plant_id={plant_id}" if plant_id else ""

    reports = [
        {
            "title": "BRSR Report",
            "description": (
                "Business Responsibility & Sustainability Report, generated live "
                "from your BRSR questionnaire."
            ),
            "accent": "blue",
            "fy": selected_year,
            "stats": [
                {"value": total_q, "label": "Questions", "color": ""},
                {"value": answered_q, "label": "Answered", "color": "blue"},
                {"value": f"{progress}%", "label": "Complete", "color": "green"},
            ],
            "pdf_url": f"{reverse('report:brsr_report_pdf')}?financial_year={fy_label}{plant_qs}",
            "excel_url": f"{reverse('report:brsr_report_excel')}?financial_year={fy_label}{plant_qs}",
            "view_url": f"{reverse('report:brsr_report_preview')}?financial_year={fy_label}{plant_qs}",
        },
    ]
    return reports


def _get_ghg_report_data(selected_year, plant_id=None):
    """
    Get GHG report data for the selected year/plant.
    This is a placeholder - you can replace with actual GHG data logic.
    """
    plant_qs = f"&plant_id={plant_id}" if plant_id else ""
    return {
        "scope1": 150,
        "scope2": 200,
        "total": 350,
        "pdf_url": "#",
        "excel_url": "#",
        "detail_url": f"{reverse('report:report_detail')}?year={selected_year}&type=ghg{plant_qs}",
    }


def _get_recent_reports_from_storage(request, selected_year, plant_id=None):
    """
    Get recent reports from global storage.
    """
    global REPORT_STORAGE

    storage_key = f"{request.user.id}_{plant_id or 'all'}_{selected_year}"
    reports = REPORT_STORAGE.get(storage_key, [])

    logger.info(f"Retrieved {len(reports)} reports from storage for plant={plant_id}, year={selected_year}")
    return reports


def _add_report_to_storage(request, selected_year, report_data, plant_id=None):
    """
    Add a generated report to global storage.
    """
    global REPORT_STORAGE

    storage_key = f"{request.user.id}_{plant_id or 'all'}_{selected_year}"
    reports = REPORT_STORAGE.get(storage_key, [])

    if not isinstance(reports, list):
        reports = []

    # Check if report already exists (avoid duplicates)
    for existing in reports:
        if existing.get("name") == report_data.get("name"):
            existing.update(report_data)
            logger.info(f"Updated existing report: {report_data.get('name')}")
            return reports

    reports.insert(0, report_data)
    reports = reports[:50]
    REPORT_STORAGE[storage_key] = reports

    logger.info(f"Added report to storage. Total reports for plant={plant_id}, year={selected_year}: {len(reports)}")
    logger.info(f"Report data: {report_data}")

    return reports


def _recent_reports(request, selected_year, plant_id=None):
    """
    Rows for the "Recent Reports" table.
    Uses global storage to track generated reports.
    """
    return _get_recent_reports_from_storage(request, selected_year, plant_id)


# ---------------------------------------------------------------------------
# Views
# ---------------------------------------------------------------------------

class ReportGenerationView(LoginRequiredMixin, TemplateView):
    """Renders report_generate.html: plant + year filters, report cards, recent reports table."""

    login_url = "accounts:login"
    template_name = "report/report_generate.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        reporting_years = _reporting_years()
        selected_year = self.request.GET.get("reporting_year") or (
            reporting_years[0] if reporting_years else "2024-25"
        )

        plants = _plants()
        selected_plant_id = _selected_plant_id(self.request, plants)

        recent_reports = _recent_reports(self.request, selected_year, selected_plant_id)
        completed_count = sum(1 for r in recent_reports if r.get("status_raw") == "completed")
        processing_count = sum(1 for r in recent_reports if r.get("status_raw") == "processing")

        ghg_report_data = _get_ghg_report_data(selected_year, selected_plant_id)

        context.update({
            "active_fy": reporting_years[0] if reporting_years else "2024-25",
            "reporting_years": reporting_years,
            "selected_year": selected_year,
            "plants": plants,
            "selected_plant_id": selected_plant_id,
            "available_reports": _available_reports(selected_year, selected_plant_id),
            "ghg_report": ghg_report_data,
            "recent_reports": recent_reports,
            "total_reports_count": len(recent_reports),
            "completed_count": completed_count,
            "processing_count": processing_count,
        })

        logger.info(f"Template context - available_reports count: {len(context['available_reports'])}")
        logger.info(f"Template context - recent_reports count: {len(recent_reports)}")
        logger.info(f"GHG Report data: {ghg_report_data}")

        return context


class ReportGenerateView(LoginRequiredMixin, View):
    """
    Handles the "Generate All" button's AJAX POST.
    Generates reports (scoped to plant + year) and stores them in global storage.
    """

    login_url = "accounts:login"

    def post(self, request, *args, **kwargs):
        reporting_year = request.POST.get("reporting_year")
        plant_id = request.POST.get("plant_id")

        if not reporting_year:
            return JsonResponse(
                {"status": "error", "message": "Please select a reporting year."}, status=400
            )
        if not plant_id:
            return JsonResponse(
                {"status": "error", "message": "Please select a plant."}, status=400
            )

        try:
            from apps.organizations.models import Plant
            plant = Plant.objects.filter(id=plant_id).first()
            plant_name = plant.name if plant else ""

            logger.info(f"Generating reports for plant={plant_id} ({plant_name}) year={reporting_year}")
            logger.info(f"User ID: {request.user.id}")

            plant_qs = f"&plant_id={plant_id}"

            # Generate BRSR Report
            brsr_report = {
                "name": f"BRSR Report - {plant_name} - FY {reporting_year}",
                "accent": "blue",
                "type": "BRSR",
                "year": reporting_year,
                "plant_id": plant_id,
                "plant_name": plant_name,
                "generated_on": timezone.now().strftime("%Y-%m-%d %H:%M"),
                "status": "Completed",
                "status_raw": "completed",
                "pdf_url": f"{reverse('report:brsr_report_pdf')}?financial_year={reporting_year}{plant_qs}",
                "excel_url": f"{reverse('report:brsr_report_excel')}?financial_year={reporting_year}{plant_qs}",
                "detail_url": f"{reverse('report:report_detail')}?year={reporting_year}&type=brsr{plant_qs}",
            }

            # Generate GHG Report
            ghg_report = {
                "name": f"GHG Report - {plant_name} - FY {reporting_year}",
                "accent": "purple",
                "type": "GHG",
                "year": reporting_year,
                "plant_id": plant_id,
                "plant_name": plant_name,
                "generated_on": timezone.now().strftime("%Y-%m-%d %H:%M"),
                "status": "Completed",
                "status_raw": "completed",
                "pdf_url": "#",  # Replace with actual GHG PDF URL when implemented
                "excel_url": "#",  # Replace with actual GHG Excel URL when implemented
                "detail_url": f"{reverse('report:report_detail')}?year={reporting_year}&type=ghg{plant_qs}",
                "scope1": 150,  # Placeholder - replace with actual data
                "scope2": 200,  # Placeholder - replace with actual data
                "total": 350,   # Placeholder - replace with actual data
            }

            _add_report_to_storage(request, reporting_year, brsr_report, plant_id)
            _add_report_to_storage(request, reporting_year, ghg_report, plant_id)

            verify_reports = _get_recent_reports_from_storage(request, reporting_year, plant_id)
            logger.info(f"After saving, found {len(verify_reports)} reports in storage")

            global REPORT_STORAGE
            logger.info(f"All storage keys: {list(REPORT_STORAGE.keys())}")

            return JsonResponse({
                "status": "success",
                "message": f"Reports for {plant_name} — FY {reporting_year} have been generated successfully.",
                "report_count": len(verify_reports),
                "reports_preview": [r["name"] for r in verify_reports[:5]],
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
        plant_id = self.request.GET.get("plant_id")

        if year and report_type:
            reports = _get_recent_reports_from_storage(self.request, year, plant_id)
            for report in reports:
                if report.get("type", "").lower() == report_type.lower():
                    context["report"] = report
                    break

        context.update({
            "pk": kwargs.get("pk"),
            "report_type": report_type,
            "year": year,
            "plant_id": plant_id,
        })
        return context


class ReportDownloadView(LoginRequiredMixin, View):
    """
    Generic download endpoint keyed by report_type + file_format, e.g.:
        /report/download/brsr/pdf/?financial_year=2024-2025&plant_id=3
        /report/download/brsr/excel/?financial_year=2024-2025&plant_id=3
        /report/download/ghg/pdf/
        /report/download/ghg/excel/

    plant_id (like financial_year) is read straight off request.GET by the
    downstream BRSR views, so nothing extra is needed here.
    """

    login_url = "accounts:login"

    def get(self, request, report_type, file_format, *args, **kwargs):
        if report_type.lower() == "brsr":
            if file_format.lower() == "pdf":
                return BRSRReportPDFDownloadView.as_view()(request)
            if file_format.lower() in ("excel", "xlsx"):
                return BRSRReportExcelDownloadView.as_view()(request)
            return JsonResponse({"detail": f"Unsupported format '{file_format}' for BRSR."}, status=400)

        if report_type.lower() == "ghg":
            return JsonResponse({
                "detail": f"GHG {file_format} download not implemented yet.",
                "status": "coming_soon"
            }, status=200)

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
        plants = _plants()
        selected_plant_id = request.GET.get("plant_id") or (str(plants[0].id) if plants else None)

        reports = _recent_reports(request, selected_year, selected_plant_id)
        ghg_data = _get_ghg_report_data(selected_year, selected_plant_id)

        return JsonResponse({
            "selected_year": selected_year,
            "selected_plant_id": selected_plant_id,
            "reporting_years": _reporting_years(),
            "plants": [{"id": p.id, "name": p.name} for p in plants],
            "available_reports": _available_reports(selected_year, selected_plant_id),
            "ghg_report": ghg_data,
            "recent_reports": reports,
            "total_reports_count": len(reports),
            "completed_count": sum(1 for r in reports if r.get("status_raw") == "completed"),
            "processing_count": sum(1 for r in reports if r.get("status_raw") == "processing"),
        })