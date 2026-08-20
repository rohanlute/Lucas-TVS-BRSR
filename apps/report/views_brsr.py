# apps/report/views_brsr.py
"""
Views that expose the live BRSR questionnaire as a report.
PDF generation uses ReportLab, Excel generation uses openpyxl -- both
matching the Lucas TVS format and both driven off the same
brsr_report_data.get_brsr_report_data() + brsr_pdf_reportlab._flatten_rows
normalization, so the two outputs can't structurally drift apart.

When plant_id is missing or "all", every view routes through
get_brsr_report_data_all_plants() instead of get_brsr_report_data(plant_id=None):
the latter's per-question "most recently updated response" logic silently
drops every plant's answer except one, whereas the "all plants" combiner
sums numeric answers and dict-collects text answers per plant so nothing
is lost -- see brsr_report_data.py for the combining logic itself.
"""

from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponse
from django.views.generic import TemplateView
import logging

from .brsr_report_data import get_brsr_report_data, get_brsr_report_data_all_plants

logger = logging.getLogger(__name__)


def _company_from_request(request):
    company = getattr(request.user, "company", None)
    return {
        "name": getattr(company, "company_name", None) or "Lucas TVS Ltd",
        "cin": getattr(company, "cin_number", None) or "",
    }


def _is_all_plants(plant_id):
    return not plant_id or plant_id == "all"


def _company_plant_ids(request):
    """
    Must mirror apps.report.views._plants() exactly, so the plant list
    shown in the dropdown and the plants actually combined into "All
    Plants" never diverge.
    """
    from apps.organizations.models import Plant

    if not request.user.is_super_admin:
        return list(
            Plant.objects.filter(
                is_active=True,
                created_by__company=request.user.company,
            ).values_list("id", flat=True)
        )
    return list(Plant.objects.filter(is_active=True).values_list("id", flat=True))


def _get_report_sections(request, financial_year, assignment_id, plant_id):
    if _is_all_plants(plant_id):
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

        try:
            report_sections = _get_report_sections(self.request, financial_year, assignment_id, plant_id)
            logger.info(f"Found {len(report_sections)} report sections")
        except Exception as e:
            logger.error(f"Error getting report data: {e}")
            report_sections = []

        context["report_sections"] = report_sections
        context["financial_year"] = financial_year or "FY 2024-25"
        context["plant_id"] = plant_id
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

        company = _company_from_request(request)

        try:
            report_sections = _get_report_sections(request, financial_year, assignment_id, plant_id)
            buffer = generate_brsr_pdf(
                financial_year=financial_year,
                assignment_id=assignment_id,
                plant_id=plant_id,
                company_name=company["name"],
                company_cin=company["cin"],
                report_sections=report_sections,
            )

            suffix = "All_Plants" if _is_all_plants(plant_id) else ""
            filename = f"Lucas_TVS_BRSR_Report_{suffix + '_' if suffix else ''}{(financial_year or 'FY2024-25').replace(' ', '_')}.pdf"
            response = HttpResponse(buffer.getvalue(), content_type="application/pdf")
            response["Content-Disposition"] = f'attachment; filename="{filename}"'
            return response
        except Exception as e:
            logger.error(f"Error generating PDF: {e}")
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

        company = _company_from_request(request)

        try:
            report_sections = _get_report_sections(request, financial_year, assignment_id, plant_id)
            buffer = generate_brsr_excel(
                financial_year=financial_year,
                assignment_id=assignment_id,
                plant_id=plant_id,
                company_name=company["name"],
                company_cin=company["cin"],
                report_sections=report_sections,
            )

            suffix = "All_Plants" if _is_all_plants(plant_id) else ""
            filename = f"Lucas_TVS_BRSR_Report_{suffix + '_' if suffix else ''}{(financial_year or 'FY2024-25').replace(' ', '_')}.xlsx"
            response = HttpResponse(
                buffer.getvalue(),
                content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
            response["Content-Disposition"] = f'attachment; filename="{filename}"'
            return response
        except Exception as e:
            logger.error(f"Error generating Excel: {e}")
            return HttpResponse(f"Error generating Excel: {str(e)}", status=500)