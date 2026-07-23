# apps/report/views_brsr.py
"""
Views that expose the live BRSR questionnaire as a report.
PDF generation uses ReportLab, Excel generation uses openpyxl -- both
matching the Lucas TVS format and both driven off the same
brsr_report_data.get_brsr_report_data() + brsr_pdf_reportlab._flatten_rows
normalization, so the two outputs can't structurally drift apart.
"""

from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponse
from django.views.generic import TemplateView
import logging

from .brsr_report_data import get_brsr_report_data

logger = logging.getLogger(__name__)


def _company_from_request(request):
    company = getattr(request.user, "company", None)
    return {
        "name": getattr(company, "company_name", None) or "Lucas TVS Ltd",
        "cin": getattr(company, "cin_number", None) or "",
    }


class BRSRReportPreviewView(LoginRequiredMixin, TemplateView):
    """On-screen HTML preview of the BRSR report."""

    login_url = "accounts:login"
    template_name = "report/brsr_report.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        financial_year = self.request.GET.get("financial_year")
        assignment_id = self.request.GET.get("assignment_id")

        # Log the parameters for debugging
        logger.info(f"BRSRReportPreviewView - financial_year: {financial_year}, assignment_id: {assignment_id}")
        
        # Get report data
        try:
            report_sections = get_brsr_report_data(
                financial_year=financial_year,
                assignment_id=assignment_id
            )
            logger.info(f"Found {len(report_sections)} report sections")
        except Exception as e:
            logger.error(f"Error getting report data: {e}")
            report_sections = []
        
        context["report_sections"] = report_sections
        context["financial_year"] = financial_year or "FY 2024-25"
        context["company_name"] = _company_from_request(self.request)["name"]
        return context


class BRSRReportPDFDownloadView(LoginRequiredMixin, TemplateView):
    """Streams the report as a PDF built with ReportLab in Lucas TVS format."""

    login_url = "accounts:login"

    def get(self, request, *args, **kwargs):
        from .brsr_pdf_reportlab import generate_brsr_pdf

        financial_year = request.GET.get("financial_year")
        assignment_id = request.GET.get("assignment_id")

        # Log the parameters for debugging
        logger.info(f"BRSRReportPDFDownloadView - financial_year: {financial_year}, assignment_id: {assignment_id}")

        company = _company_from_request(request)

        try:
            buffer = generate_brsr_pdf(
                financial_year=financial_year,
                assignment_id=assignment_id,
                company_name=company["name"],
                company_cin=company["cin"],
            )

            filename = f"Lucas_TVS_BRSR_Report_{(financial_year or 'FY2024-25').replace(' ', '_')}.pdf"
            response = HttpResponse(buffer.getvalue(), content_type="application/pdf")
            response["Content-Disposition"] = f'attachment; filename="{filename}"'
            return response
        except Exception as e:
            logger.error(f"Error generating PDF: {e}")
            # Return error response
            return HttpResponse(f"Error generating PDF: {str(e)}", status=500)


class BRSRReportExcelDownloadView(LoginRequiredMixin, TemplateView):
    """
    Streams the report as an .xlsx workbook built with openpyxl, matching
    the PDF's structure: one sheet per Section A/B and per Principle, with
    matrix (P1-P9) and table-shaped answers rendered as real grids -- not
    flattened into a single "Answer" column like the previous version.
    """

    login_url = "accounts:login"

    def get(self, request, *args, **kwargs):
        from .brsr_excel_openpyxl import generate_brsr_excel

        financial_year = request.GET.get("financial_year")
        assignment_id = request.GET.get("assignment_id")

        # Log the parameters for debugging
        logger.info(f"BRSRReportExcelDownloadView - financial_year: {financial_year}, assignment_id: {assignment_id}")

        company = _company_from_request(request)

        try:
            buffer = generate_brsr_excel(
                financial_year=financial_year,
                assignment_id=assignment_id,
                company_name=company["name"],
                company_cin=company["cin"],
            )

            filename = f"Lucas_TVS_BRSR_Report_{(financial_year or 'FY2024-25').replace(' ', '_')}.xlsx"
            response = HttpResponse(
                buffer.getvalue(),
                content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
            response["Content-Disposition"] = f'attachment; filename="{filename}"'
            return response
        except Exception as e:
            logger.error(f"Error generating Excel: {e}")
            # Return error response
            return HttpResponse(f"Error generating Excel: {str(e)}", status=500)