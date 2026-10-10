# apps/report/views_brsr.py
"""
Views that expose the live BRSR questionnaire as a report.
PDF generation uses ReportLab, Excel generation uses openpyxl -- both driven
off the same report data + brsr_pdf_reportlab._flatten_rows normalization.

PLANT-WISE vs OVERALL
---------------------
- plant_id = a specific plant id  -> report for THAT plant only
                                      (get_brsr_report_data).
- plant_id missing or "all"       -> overall report combining every plant of
                                      the user's company
                                      (get_brsr_report_data_all_plants):
                                      numeric answers are summed, text
                                      answers are listed per plant.

The plant name ("All Plants" or the plant's own name) is printed on the
PDF cover / page header and the Excel overview, and is part of the
download filename.
"""

import logging
import re

from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponse
from django.views.generic import TemplateView

from .plant_scope import company_plant_ids
from .brsr_report_data import (
    _reportable_brsr_assignments,
    get_brsr_report_data,
    get_brsr_report_data_all_plants,
    get_plants_with_data,
)

logger = logging.getLogger(__name__)

ALL_PLANTS_LABEL = "All Plants"


def _company_from_request(request):
    company = getattr(request.user, "company", None)
    return {
        "name": getattr(company, "company_name", None) or "Lucas TVS Ltd",
        "cin": getattr(company, "cin_number", None) or "",
    }


def _is_all_plants(plant_id):
    return not plant_id or plant_id == "all"


def _company_plant_ids(request):
    """Plants this user may report on -- shared with views.py (plant_scope.py),
    so the dropdown and the "All Plants" report always use the same list."""
    return company_plant_ids(request.user)


def _resolve_plant(request, plant_id):
    """
    Returns (plant_name, error_message).

    - "all"/missing  -> ("All Plants", None)
    - valid plant the user may access -> (plant.name, None)
    - unknown plant, or one outside the user's company -> (None, message)
    """
    if _is_all_plants(plant_id):
        return ALL_PLANTS_LABEL, None

    from apps.organizations.models import Plant

    try:
        pid = int(plant_id)
    except (TypeError, ValueError):
        return None, "Invalid plant selected."

    if pid not in _company_plant_ids(request):
        return None, "Plant not found or you do not have access to it."

    plant = Plant.objects.filter(id=pid).first()
    if not plant:
        return None, "Plant not found."
    return plant.name, None


def _has_reportable_data(request, financial_year, assignment_id, plant_id):
    """True if at least one submitted (reportable) assignment exists for the
    selected plant (or any of the company's plants for "All Plants")."""
    qs = _reportable_brsr_assignments(
        financial_year=financial_year,
        assignment_id=assignment_id,
        plant_id=None if _is_all_plants(plant_id) else plant_id,
    )
    if _is_all_plants(plant_id):
        qs = qs.filter(plant_id__in=_company_plant_ids(request))
    return qs.exists()


def _plants_covered(request, financial_year, assignment_id, plant_id):
    """
    Plants an "All Plants" report really covers: the user's company plants
    that have submitted data for the year. Empty list for a single-plant
    report.
    """
    if not _is_all_plants(plant_id):
        return []
    return get_plants_with_data(
        financial_year=financial_year,
        assignment_id=assignment_id,
        plant_ids=_company_plant_ids(request),
    )


def _get_report_sections(request, financial_year, assignment_id, plant_id):
    if _is_all_plants(plant_id):
        # Pass ALL of the company's plants; the combiner itself picks the
        # plants that have data and also folds in company-wide answers.
        return get_brsr_report_data_all_plants(
            financial_year=financial_year,
            assignment_id=assignment_id,
            plant_ids=_company_plant_ids(request),
        )
    return get_brsr_report_data(
        financial_year=financial_year,
        assignment_id=assignment_id,
        plant_id=plant_id,
    )


def _safe_filename_part(value):
    return re.sub(r"[^A-Za-z0-9]+", "_", str(value)).strip("_")


def _build_filename(plant_name, financial_year, ext):
    plant_part = "All_Plants" if plant_name == ALL_PLANTS_LABEL else _safe_filename_part(plant_name)
    fy_part = _safe_filename_part(financial_year or "FY2024-25")
    return f"Lucas_TVS_BRSR_Report_{plant_part}_{fy_part}.{ext}"


class BRSRReportPreviewView(LoginRequiredMixin, TemplateView):
    login_url = "accounts:login"
    template_name = "report/brsr_report.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        financial_year = self.request.GET.get("financial_year")
        assignment_id = self.request.GET.get("assignment_id")
        plant_id = self.request.GET.get("plant_id")

        logger.info(
            f"BRSRReportPreviewView - financial_year: {financial_year}, "
            f"assignment_id: {assignment_id}, plant_id: {plant_id}"
        )

        plant_name, error = _resolve_plant(self.request, plant_id)

        report_sections = []
        if error:
            logger.warning(f"Preview blocked: {error}")
        else:
            try:
                report_sections = _get_report_sections(self.request, financial_year, assignment_id, plant_id)
                logger.info(f"Found {len(report_sections)} report sections")
            except Exception:
                logger.exception("Error getting report data")

        context["plants_covered"] = [
            p.name for p in _plants_covered(self.request, financial_year, assignment_id, plant_id)
        ] if not error else []
        context["report_sections"] = report_sections
        context["financial_year"] = financial_year or "FY 2024-25"
        context["plant_id"] = plant_id
        context["plant_name"] = plant_name or ""
        context["is_all_plants"] = _is_all_plants(plant_id)
        context["report_error"] = error
        context["company_name"] = _company_from_request(self.request)["name"]
        return context


class BRSRReportPDFDownloadView(LoginRequiredMixin, TemplateView):
    login_url = "accounts:login"

    def get(self, request, *args, **kwargs):
        from .brsr_pdf_reportlab import generate_brsr_pdf

        financial_year = request.GET.get("financial_year")
        assignment_id = request.GET.get("assignment_id")
        plant_id = request.GET.get("plant_id")

        logger.info(
            f"BRSRReportPDFDownloadView - financial_year: {financial_year}, "
            f"assignment_id: {assignment_id}, plant_id: {plant_id}"
        )

        plant_name, error = _resolve_plant(request, plant_id)
        if error:
            return HttpResponse(error, status=404)

        if not _has_reportable_data(request, financial_year, assignment_id, plant_id):
            return HttpResponse(
                f"No submitted BRSR data found for {plant_name} "
                f"({financial_year or 'selected year'}).",
                status=404,
            )

        company = _company_from_request(request)

        try:
            report_sections = _get_report_sections(request, financial_year, assignment_id, plant_id)
            covered = [p.name for p in _plants_covered(request, financial_year, assignment_id, plant_id)]
            buffer = generate_brsr_pdf(
                financial_year=financial_year,
                assignment_id=assignment_id,
                plant_id=plant_id,
                company_name=company["name"],
                company_cin=company["cin"],
                report_sections=report_sections,
                plant_name=plant_name,
                plants_included=covered,
            )

            filename = _build_filename(plant_name, financial_year, "pdf")
            response = HttpResponse(buffer.getvalue(), content_type="application/pdf")
            response["Content-Disposition"] = f'attachment; filename="{filename}"'
            return response
        except Exception as e:
            logger.exception("Error generating PDF")
            return HttpResponse(f"Error generating PDF: {str(e)}", status=500)


class BRSRReportExcelDownloadView(LoginRequiredMixin, TemplateView):
    login_url = "accounts:login"

    def get(self, request, *args, **kwargs):
        from .brsr_excel_openpyxl import generate_brsr_excel

        financial_year = request.GET.get("financial_year")
        assignment_id = request.GET.get("assignment_id")
        plant_id = request.GET.get("plant_id")

        logger.info(
            f"BRSRReportExcelDownloadView - financial_year: {financial_year}, "
            f"assignment_id: {assignment_id}, plant_id: {plant_id}"
        )

        plant_name, error = _resolve_plant(request, plant_id)
        if error:
            return HttpResponse(error, status=404)

        if not _has_reportable_data(request, financial_year, assignment_id, plant_id):
            return HttpResponse(
                f"No submitted BRSR data found for {plant_name} "
                f"({financial_year or 'selected year'}).",
                status=404,
            )

        company = _company_from_request(request)

        try:
            report_sections = _get_report_sections(request, financial_year, assignment_id, plant_id)
            covered = [p.name for p in _plants_covered(request, financial_year, assignment_id, plant_id)]
            buffer = generate_brsr_excel(
                financial_year=financial_year,
                assignment_id=assignment_id,
                plant_id=plant_id,
                company_name=company["name"],
                company_cin=company["cin"],
                report_sections=report_sections,
                plant_name=plant_name,
                plants_included=covered,
            )

            filename = _build_filename(plant_name, financial_year, "xlsx")
            response = HttpResponse(
                buffer.getvalue(),
                content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
            response["Content-Disposition"] = f'attachment; filename="{filename}"'
            return response
        except Exception as e:
            logger.exception("Error generating Excel")
            return HttpResponse(f"Error generating Excel: {str(e)}", status=500)