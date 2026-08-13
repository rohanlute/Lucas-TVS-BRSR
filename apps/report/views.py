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

from .brsr_report_data import get_brsr_report_data, get_brsr_stats

logger = logging.getLogger(__name__)

# Global in-memory storage for reports (for debugging)
REPORT_STORAGE = {}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _reporting_years():
    """Years shown in the 'Reporting Year' dropdown."""
    from apps.organizations.models import FinancialYear
    years = list(FinancialYear.objects.order_by("-start_date").values_list("financial_year", flat=True))
    return years or ["2024-2025"]


def _plants(request=None):
    """
    Plants shown in the 'Plant' dropdown.
    Filter by user's company if not superadmin.
    """
    from apps.organizations.models import Plant

    if request and not request.user.is_super_admin:
        return list(Plant.objects.filter(
            is_active=True,
            created_by__company=request.user.company
        ).order_by("name"))

    return list(Plant.objects.filter(is_active=True).order_by("name"))


def _selected_plant_id(request, plants):
    """Resolves the active plant_id from GET or POST."""
    plant_id = request.GET.get("plant_id") or request.POST.get("plant_id")
    if plant_id:
        return plant_id
    return "all"  # Default to "all"


def _get_plant_name(plant_id):
    """Get plant name from plant_id, returns 'All Plants' for 'all' or None."""
    if plant_id == "all":
        return "All Plants"

    from apps.organizations.models import Plant
    plant = Plant.objects.filter(id=plant_id).first()
    return plant.name if plant else "Unknown Plant"


def _get_plant_display_name(plant_id):
    """Get display name for the section label."""
    if plant_id == "all":
        return "All Plants"

    from apps.organizations.models import Plant
    plant = Plant.objects.filter(id=plant_id).first()
    return plant.name if plant else ""


# ---------------------------------------------------------------------------
# Report card stats
# ---------------------------------------------------------------------------
#
# This used to derive total/answered by walking get_brsr_report_data()'s
# output. That's the wrong source: get_brsr_report_data() deliberately
# filters each section down to only rows that already have a submitted
# answer (so the report/PDF never renders blank questions) — which means
# "total" reconstructed from it is always silently equal to "answered",
# never the real question-bank size (e.g. 128).
#
# get_brsr_stats() (in brsr_report_data.py) queries the full active
# question set directly and reuses the same _row_has_data() logic the
# report itself uses to decide "answered" — correctly counting answers
# that live in sub_questions / table_rows / matrix_rows for table, matrix,
# and checkbox_group question types, not just a row's own top-level
# answer_value.

def _brsr_report_stats(financial_year, plant_id=None):
    """
    Quick counts to show on the BRSR report card: total questions,
    how many have an answer, and progress %.
    """
    from apps.organizations.models import Plant

    logger.info("=== _brsr_report_stats called ===")
    logger.info(f"financial_year: {financial_year}, plant_id: {plant_id}")

    # If plant_id is "all", aggregate across all plants
    if plant_id == "all":
        plants = Plant.objects.filter(is_active=True)
        logger.info(f"Found {plants.count()} active plants for 'all' aggregation")

        total = 0
        answered = 0

        for plant in plants:
            try:
                logger.info(f"Fetching stats for plant: {plant.id} - {plant.name}")
                plant_total, plant_answered = get_brsr_stats(
                    financial_year=financial_year,
                    plant_id=plant.id
                )
                logger.info(
                    f"Plant {plant.id} ({plant.name}): "
                    f"total={plant_total}, answered={plant_answered}"
                )

                total += plant_total
                answered += plant_answered

            except Exception:
                # Log the FULL traceback (not just str(e)) so a real bug
                # doesn't get hidden behind a generic one-line message.
                logger.exception(
                    f"Error getting BRSR stats for plant {plant.id} "
                    f"(financial_year={financial_year})"
                )
                continue

        progress = round((answered / total * 100), 1) if total else 0
        logger.info(f"All plants stats - Total: {total}, Answered: {answered}, Progress: {progress}%")
        return total, answered, progress

    else:
        # Single plant
        try:
            logger.info(f"Fetching stats for single plant: {plant_id}")
            total, answered = get_brsr_stats(
                financial_year=financial_year,
                plant_id=plant_id
            )
            progress = round((answered / total * 100), 1) if total else 0

            logger.info(f"Single plant stats - Total: {total}, Answered: {answered}, Progress: {progress}%")
            return total, answered, progress

        except Exception:
            logger.exception(
                f"Error fetching BRSR stats for plant {plant_id} "
                f"(financial_year={financial_year})"
            )
            return 0, 0, 0


def _available_reports(selected_year, plant_id=None, request=None):
    """Returns the BRSR report card data."""
    fy_label = selected_year
    total_q, answered_q, progress = _brsr_report_stats(selected_year, plant_id)

    logger.info("=== _available_reports results ===")
    logger.info(f"total_q: {total_q}, answered_q: {answered_q}, progress: {progress}")

    # Build plant query string
    if plant_id and plant_id != "all":
        plant_qs = f"&plant_id={plant_id}"
    else:
        plant_qs = ""

    # Get plant name for display
    plant_display = _get_plant_display_name(plant_id)
    title_suffix = f" - {plant_display}" if plant_display else ""

    reports = [
        {
            "title": f"BRSR Report{title_suffix}",
            "description": (
                "Business Responsibility & Sustainability Report, generated live "
                "from your BRSR questionnaire."
            ),
            "accent": "blue",
            "fy": selected_year,
            "stats": [
                {"value": total_q, "label": "Total Questions", "color": ""},
                {"value": answered_q, "label": "Answered", "color": "blue"},
                {"value": f"{progress}%", "label": "Completion", "color": "green"},
            ],
            "total_questions": total_q,
            "answered_questions": answered_q,
            "completion_percentage": progress,
            "pdf_url": f"{reverse('report:brsr_report_pdf')}?financial_year={fy_label}{plant_qs}",
            "excel_url": f"{reverse('report:brsr_report_excel')}?financial_year={fy_label}{plant_qs}",
            "view_url": f"{reverse('report:brsr_report_preview')}?financial_year={fy_label}{plant_qs}",
        },
    ]
    return reports


def _build_brsr_report_entry(plant_id, plant_name, reporting_year):
    """
    Builds one Recent-Reports row for a BRSR report, using REAL completion
    data from get_brsr_stats() instead of a hardcoded "Completed" status.

    status_raw is derived honestly from how much of the questionnaire is
    actually answered:
      - "completed"  -> 100% of applicable questions answered
      - "processing" -> some but not all answered
      - "draft"      -> nothing answered yet
    """
    total, answered = get_brsr_stats(
        financial_year=reporting_year,
        plant_id=None if plant_id in (None, "all") else plant_id,
    )
    progress = round((answered / total * 100), 1) if total else 0

    if total and answered >= total:
        status_raw, status = "completed", "Completed"
    elif answered > 0:
        status_raw, status = "processing", "In Progress"
    else:
        status_raw, status = "draft", "Draft"

    plant_qs = f"&plant_id={plant_id}" if plant_id and plant_id != "all" else ""

    return {
        "name": f"BRSR Report - {plant_name} - FY {reporting_year}",
        "accent": "blue",
        "type": "BRSR",
        "year": reporting_year,
        "plant_id": str(plant_id) if plant_id else "all",
        "plant_name": plant_name,
        "generated_on": timezone.now().strftime("%Y-%m-%d %H:%M"),
        "status": status,
        "status_raw": status_raw,
        "total_questions": total,
        "answered_questions": answered,
        "completion_percentage": progress,
        "pdf_url": f"{reverse('report:brsr_report_pdf')}?financial_year={reporting_year}{plant_qs}",
        "excel_url": f"{reverse('report:brsr_report_excel')}?financial_year={reporting_year}{plant_qs}",
        "detail_url": f"{reverse('report:report_detail')}?year={reporting_year}&type=brsr{plant_qs}",
    }


def _build_ghg_report_entry(plant_id, plant_name, reporting_year):
    """
    Builds one Recent-Reports row for a GHG report.

    NOTE: there's no live GHG data source wired up yet (_get_ghg_report_data
    below still returns fixed scope1/scope2/total figures) -- this just
    centralizes that placeholder in one place instead of duplicating the
    same hardcoded numbers in every call site, so a real GHG calculation
    only needs to be plugged in here once it exists. Status is left as
    "processing" rather than "Completed" to avoid overstating a report
    that isn't backed by real numbers yet.
    """
    plant_qs = f"&plant_id={plant_id}" if plant_id and plant_id != "all" else ""

    return {
        "name": f"GHG Report - {plant_name} - FY {reporting_year}",
        "accent": "purple",
        "type": "GHG",
        "year": reporting_year,
        "plant_id": str(plant_id) if plant_id else "all",
        "plant_name": plant_name,
        "generated_on": timezone.now().strftime("%Y-%m-%d %H:%M"),
        "status": "In Progress",
        "status_raw": "processing",
        "pdf_url": "#",
        "excel_url": "#",
        "detail_url": f"{reverse('report:report_detail')}?year={reporting_year}&type=ghg{plant_qs}",
        "scope1": 150,
        "scope2": 200,
        "total": 350,
    }


def _get_ghg_report_data(selected_year, plant_id=None):
    """Get GHG report data for the selected year/plant."""
    if plant_id and plant_id != "all":
        plant_qs = f"&plant_id={plant_id}"
    else:
        plant_qs = ""

    return {
        "scope1": 150,
        "scope2": 200,
        "total": 350,
        "pdf_url": "#",
        "excel_url": "#",
        "detail_url": f"{reverse('report:report_detail')}?year={selected_year}&type=ghg{plant_qs}",
    }


def _get_recent_reports_from_storage(request, selected_year, plant_id=None):
    """Get recent reports from global storage."""
    global REPORT_STORAGE

    storage_key = f"{request.user.id}_{plant_id or 'all'}_{selected_year}"
    reports = REPORT_STORAGE.get(storage_key, [])

    logger.info(f"Retrieved {len(reports)} reports from storage for plant={plant_id}, year={selected_year}")
    return reports


def _add_report_to_storage(request, selected_year, report_data, plant_id=None):
    """Add a generated report to global storage."""
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
    reports = reports[:2]
    REPORT_STORAGE[storage_key] = reports

    logger.info(f"Added report to storage. Total reports for plant={plant_id}, year={selected_year}: {len(reports)}")
    return reports


def _recent_reports(request, selected_year, plant_id=None):
    """Rows for the 'Recent Reports' table."""
    # If plant_id is "all", get reports for all plants
    if plant_id == "all":
        from apps.organizations.models import Plant

        # Get plants based on user's company
        if not request.user.is_super_admin:
            plants = Plant.objects.filter(
                is_active=True,
                created_by__company=request.user.company
            )
        else:
            plants = Plant.objects.filter(is_active=True)

        all_reports = []

        # Reports logged directly under the "all" aggregate key -- this is
        # where a download triggered while "All Plants" is selected gets
        # written (see ReportTrackDownloadView), so it must be read back
        # here too, not just the individual per-plant keys below.
        all_reports.extend(_get_recent_reports_from_storage(request, selected_year, "all"))

        for plant in plants:
            plant_reports = _get_recent_reports_from_storage(request, selected_year, str(plant.id))
            all_reports.extend(plant_reports)

        # Sort by generated_on descending
        all_reports.sort(key=lambda x: x.get("generated_on", ""), reverse=True)
        return all_reports[:2]  # Limit to 2 most recent

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

        logger.info("=" * 60)
        logger.info("ReportGenerationView.get_context_data() called")
        logger.info("=" * 60)

        reporting_years = _reporting_years()
        selected_year = self.request.GET.get("reporting_year") or (
            reporting_years[0] if reporting_years else "2024-25"
        )

        # Get plants with user context
        plants = _plants(self.request)
        selected_plant_id = _selected_plant_id(self.request, plants)

        logger.info(f"selected_year: {selected_year}")
        logger.info(f"selected_plant_id: {selected_plant_id}")

        recent_reports = _recent_reports(self.request, selected_year, selected_plant_id)
        completed_count = sum(1 for r in recent_reports if r.get("status_raw") == "completed")
        processing_count = sum(1 for r in recent_reports if r.get("status_raw") == "processing")

        ghg_report_data = _get_ghg_report_data(selected_year, selected_plant_id)
        available_reports = _available_reports(selected_year, selected_plant_id, self.request)

        # Get plant display name for section label
        plant_display_name = _get_plant_display_name(selected_plant_id)

        # Calculate totals for the section label
        total_questions = 0
        answered_questions = 0
        completion_percentage = 0
        if available_reports:
            total_questions = available_reports[0].get("total_questions", 0)
            answered_questions = available_reports[0].get("answered_questions", 0)
            completion_percentage = available_reports[0].get("completion_percentage", 0)

        logger.info(
            f"📊 Final Stats - Total: {total_questions}, "
            f"Answered: {answered_questions}, Completion: {completion_percentage}%"
        )

        context.update({
            "active_fy": reporting_years[0] if reporting_years else "2024-25",
            "reporting_years": reporting_years,
            "selected_year": selected_year,
            "plants": plants,
            "selected_plant_id": selected_plant_id,
            "available_reports": available_reports,
            "ghg_report": ghg_report_data,
            "recent_reports": recent_reports,
            "total_reports_count": len(recent_reports),
            "completed_count": completed_count,
            "processing_count": processing_count,
            # For section label
            "plant_display_name": plant_display_name,
            "total_questions": total_questions,
            "answered_questions": answered_questions,
            "completion_percentage": completion_percentage,
        })

        logger.info(f"Context keys: {list(context.keys())}")
        logger.info(f"total_questions in context: {context.get('total_questions')}")
        logger.info(f"answered_questions in context: {context.get('answered_questions')}")
        logger.info(f"completion_percentage in context: {context.get('completion_percentage')}")
        logger.info("=" * 60)

        return context


class ReportGenerateView(LoginRequiredMixin, View):
    """Handles the 'Generate All' button's AJAX POST."""

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

            # Handle "All Plants" case
            if plant_id == "all":
                # Get plants based on user's company
                if not request.user.is_super_admin:
                    plants = Plant.objects.filter(
                        is_active=True,
                        created_by__company=request.user.company
                    )
                else:
                    plants = Plant.objects.filter(is_active=True)

                if not plants.exists():
                    return JsonResponse({
                        "status": "error",
                        "message": "No active plants found."
                    }, status=400)

                generated_count = 0
                for plant in plants:
                    plant_name = plant.name

                    brsr_report = _build_brsr_report_entry(str(plant.id), plant_name, reporting_year)
                    ghg_report = _build_ghg_report_entry(str(plant.id), plant_name, reporting_year)

                    _add_report_to_storage(request, reporting_year, brsr_report, str(plant.id))
                    _add_report_to_storage(request, reporting_year, ghg_report, str(plant.id))
                    generated_count += 2

                return JsonResponse({
                    "status": "success",
                    "message": f"Generated {generated_count} reports for all plants — FY {reporting_year}.",
                    "report_count": generated_count,
                })

            else:
                # Original logic for single plant
                plant = Plant.objects.filter(id=plant_id).first()
                if not plant:
                    return JsonResponse({
                        "status": "error",
                        "message": "Plant not found."
                    }, status=404)

                plant_name = plant.name

                brsr_report = _build_brsr_report_entry(plant_id, plant_name, reporting_year)
                ghg_report = _build_ghg_report_entry(plant_id, plant_name, reporting_year)

                _add_report_to_storage(request, reporting_year, brsr_report, plant_id)
                _add_report_to_storage(request, reporting_year, ghg_report, plant_id)

                verify_reports = _get_recent_reports_from_storage(request, reporting_year, plant_id)
                logger.info(f"After saving, found {len(verify_reports)} reports in storage")

                return JsonResponse({
                    "status": "success",
                    "message": f"Reports for {plant_name} — FY {reporting_year} have been generated successfully.",
                    "report_count": len(verify_reports),
                    "reports_preview": [r["name"] for r in verify_reports[:5]],
                })

        except Exception as e:
            logger.exception("Error generating reports")
            return JsonResponse({
                "status": "error",
                "message": f"Error generating reports: {str(e)}",
            }, status=500)


class ReportTrackDownloadView(LoginRequiredMixin, View):
    """
    Logs exactly ONE Recent-Reports entry for whichever report was actually
    downloaded (BRSR or GHG, PDF or Excel) -- called by a small JS hook on
    each download link.

    This exists because previously the Recent Reports table was ONLY ever
    populated by the "Generate All" button, which unconditionally wrote a
    BRSR row *and* a GHG row together with a hardcoded "Completed" status,
    regardless of which report (if any) the user actually opened. Clicking
    an individual "Download PDF"/"Download Excel" link did nothing to the
    table at all. Now each download writes its own honest entry for just
    that report type, reusing the same real-stats builders as Generate All
    so the numbers/status shown match what was actually downloaded.
    """

    login_url = "accounts:login"

    def post(self, request, *args, **kwargs):
        report_type = (request.POST.get("report_type") or "").lower()
        reporting_year = request.POST.get("reporting_year")
        plant_id = request.POST.get("plant_id") or "all"

        if report_type not in ("brsr", "ghg"):
            return JsonResponse(
                {"status": "error", "message": "Unknown report_type."}, status=400
            )
        if not reporting_year:
            return JsonResponse(
                {"status": "error", "message": "Missing reporting_year."}, status=400
            )

        try:
            from apps.organizations.models import Plant

            if plant_id and plant_id != "all":
                plant = Plant.objects.filter(id=plant_id).first()
                if not plant:
                    return JsonResponse(
                        {"status": "error", "message": "Plant not found."}, status=404
                    )
                plant_name = plant.name
                target_plant_id = plant_id
            else:
                plant_name = "All Plants"
                target_plant_id = "all"

            if report_type == "brsr":
                entry = _build_brsr_report_entry(target_plant_id, plant_name, reporting_year)
            else:
                entry = _build_ghg_report_entry(target_plant_id, plant_name, reporting_year)

            _add_report_to_storage(request, reporting_year, entry, target_plant_id)

            return JsonResponse({"status": "success", "report": entry["name"]})

        except Exception:
            logger.exception("Error tracking report download")
            return JsonResponse(
                {"status": "error", "message": "Could not record this download."}, status=500
            )


class ReportDetailView(LoginRequiredMixin, TemplateView):
    """Detail page for a single generated report."""

    login_url = "accounts:login"
    template_name = "report/report_detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        report_type = self.request.GET.get("type")
        year = self.request.GET.get("year")
        plant_id = self.request.GET.get("plant_id")

        if year and report_type:
            reports = _recent_reports(self.request, year, plant_id)
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
    """Generic download endpoint keyed by report_type + file_format."""

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
    """JSON endpoint for populating the dashboard via AJAX."""

    login_url = "accounts:login"

    def get(self, request, *args, **kwargs):
        selected_year = request.GET.get("reporting_year") or (
            _reporting_years()[0] if _reporting_years() else "2024-25"
        )
        plants = _plants(request)
        selected_plant_id = request.GET.get("plant_id") or "all"

        reports = _recent_reports(request, selected_year, selected_plant_id)
        ghg_data = _get_ghg_report_data(selected_year, selected_plant_id)

        completed_count = sum(1 for r in reports if r.get("status_raw") == "completed")
        processing_count = sum(1 for r in reports if r.get("status_raw") == "processing")

        return JsonResponse({
            "selected_year": selected_year,
            "selected_plant_id": selected_plant_id,
            "reporting_years": _reporting_years(),
            "plants": [{"id": p.id, "name": p.name} for p in plants],
            "available_reports": _available_reports(selected_year, selected_plant_id, request),
            "ghg_report": ghg_data,
            "recent_reports": reports,
            "total_reports_count": len(reports),
            "completed_count": completed_count,
            "processing_count": processing_count,
        })