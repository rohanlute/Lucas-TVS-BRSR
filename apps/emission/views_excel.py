"""
views_excel.py

Two endpoints:
  GET  /emission/api/scope-template/download/?scope=<code>&assignment=<id>
  POST /emission/api/scope-template/upload/   (multipart, field name "file",
        plus scope=<id> and optionally assignment=<id>)
"""

from django.http import HttpResponse, JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_GET, require_POST
from django.views.decorators.csrf import csrf_exempt
from decimal import Decimal
from django.utils import timezone
import logging

from .excel_template_service import (
    build_scope_template_workbook,
    parse_scope_template_workbook,
)

# Import models from your app
from apps.companies.models import Company
from apps.organizations.models import (
    FinancialYear,
    FinancialMonth,
    Plant,
)
from apps.calculator.models import Unit

# Import the emission models
from .models import (
    EmissionScope,
    EmissionCategory,
    EmissionActivity,
    EmissionSource,
    EmissionFactor,
    EmissionAssignment,
    EmissionTransaction,
    EmissionAssignmentSource,
)

logger = logging.getLogger(__name__)


def _load_categories_for_scope(scope):
    """
    Build the small view-model the template builder expects:
    category.activities_list -> activity.sources_list, activity.unit,
    activity.base_unit_id, activity.factor_for(source).
    """
    categories = EmissionCategory.objects.filter(
        scope=scope,
        is_active=True
    ).order_by("display_order")

    result = []
    for category in categories:
        activities = EmissionActivity.objects.filter(
            category=category,
            is_active=True,
            allow_excel_import=True
        ).order_by("display_order")

        wrapped_activities = []
        for activity in activities:
            sources = list(EmissionSource.objects.filter(
                activity=activity,
                is_active=True
            ).order_by("display_order"))

            activity.sources_list = sources

            def factor_for(source):
                """Get emission factor for a given source."""
                if source and activity.requires_emission_factor:
                    factor_obj = EmissionFactor.objects.filter(
                        activity=activity,
                        is_active=True,
                        effective_from__lte=timezone.now().date()
                    ).order_by("-effective_from").first()
                    if factor_obj:
                        return factor_obj.emission_factor
                return Decimal('0')

            activity.factor_for = factor_for
            wrapped_activities.append(activity)

        category.activities_list = wrapped_activities
        result.append(category)

    return result


@login_required
@require_GET
def download_scope_template(request):
    """Download Excel template for a specific emission scope."""
    scope_code = request.GET.get("scope")  # "S1", "S2", or "S3"
    assignment_id = request.GET.get("assignment")

    if not scope_code:
        return JsonResponse(
            {"success": False, "message": "Scope code is required (S1, S2, or S3)."},
            status=400
        )

    try:
        scope = EmissionScope.objects.get(code=scope_code, is_active=True)
    except EmissionScope.DoesNotExist:
        return JsonResponse(
            {"success": False, "message": f"Scope with code '{scope_code}' not found."},
            status=404
        )

    categories = _load_categories_for_scope(scope)

    company = getattr(request.user, "company", None)
    if not company:
        company = Company.objects.first()

    if not company:
        return JsonResponse(
            {"success": False, "message": "No company found."},
            status=400
        )

    plants = Plant.objects.all().order_by("name")
    financial_years = FinancialYear.objects.order_by("-financial_year")
    financial_months = FinancialMonth.objects.order_by("id")

    assignment = None
    if assignment_id:
        assignment = EmissionAssignment.objects.filter(
            id=assignment_id,
            company=company
        ).first()

    buf, filename = build_scope_template_workbook(
        scope=scope,
        categories=categories,
        company=company,
        plants=list(plants),
        financial_years=list(financial_years),
        financial_months=list(financial_months),
        assignment=assignment,
    )

    response = HttpResponse(
        buf.read(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


@login_required
@require_POST
def upload_scope_template(request):
    """
    Parse an uploaded, filled-in Excel template and return the data as
    JSON so the frontend can populate the data entry grid.
    """
    logger.info("Upload template request received")
    
    uploaded = request.FILES.get("file")
    if not uploaded:
        logger.warning("No file in request")
        return JsonResponse(
            {"success": False, "message": "No file uploaded. Please select an Excel file."},
            status=400
        )

    # Check file extension
    if not uploaded.name.endswith(('.xlsx', '.xls')):
        logger.warning(f"Invalid file type: {uploaded.name}")
        return JsonResponse(
            {"success": False, "message": "Invalid file format. Please upload an Excel file (.xlsx or .xls)."},
            status=400
        )

    assignment_id = request.POST.get("assignment") or None
    logger.info(f"Assignment ID from request: {assignment_id}")

    try:
        parsed = parse_scope_template_workbook(uploaded)
        logger.info(f"Parsed {len(parsed.get('rows', []))} rows from Excel")
    except ValueError as exc:
        logger.error(f"Parse error: {str(exc)}")
        return JsonResponse(
            {"success": False, "message": str(exc)},
            status=400
        )
    except Exception as exc:
        logger.error(f"Unexpected error parsing Excel: {str(exc)}")
        return JsonResponse(
            {"success": False, "message": f"Error reading Excel file: {str(exc)}"},
            status=400
        )

    company = getattr(request.user, "company", None)
    if not company:
        company = Company.objects.first()

    if not company:
        return JsonResponse(
            {"success": False, "message": "No company found for this user."},
            status=400
        )

    # Get or create context values
    plant_name = parsed.get("plant_name")
    financial_year_val = parsed.get("financial_year")
    financial_month_val = parsed.get("financial_month")

    if not plant_name:
        return JsonResponse(
            {"success": False, "message": "Plant name not found in the Excel file."},
            status=400
        )

    plant = Plant.objects.filter(name=plant_name).first()
    if not plant:
        # Try case-insensitive match
        plant = Plant.objects.filter(name__iexact=plant_name).first()
        if not plant:
            return JsonResponse(
                {"success": False, "message": f"Plant '{plant_name}' not found in the system."},
                status=400
            )

    if not financial_year_val:
        return JsonResponse(
            {"success": False, "message": "Financial year not found in the Excel file."},
            status=400
        )

    financial_year = FinancialYear.objects.filter(financial_year=financial_year_val).first()
    if not financial_year:
        # Try to parse as string
        try:
            fy_str = str(financial_year_val)
            financial_year = FinancialYear.objects.filter(financial_year=fy_str).first()
        except:
            pass
        
        if not financial_year:
            return JsonResponse(
                {"success": False, "message": f"Financial year '{financial_year_val}' not found in the system."},
                status=400
            )

    if not financial_month_val:
        return JsonResponse(
            {"success": False, "message": "Financial month not found in the Excel file."},
            status=400
        )

    financial_month = FinancialMonth.objects.filter(month_name=financial_month_val).first()
    if not financial_month:
        # Try case-insensitive
        financial_month = FinancialMonth.objects.filter(month_name__iexact=financial_month_val).first()
        if not financial_month:
            return JsonResponse(
                {"success": False, "message": f"Financial month '{financial_month_val}' not found in the system."},
                status=400
            )

    if not parsed.get("rows"):
        return JsonResponse(
            {"success": False, "message": "No quantities were entered in the Excel file."},
            status=400
        )

    assignment = None
    if assignment_id:
        assignment = EmissionAssignment.objects.filter(
            id=assignment_id,
            company=company,
            plant=plant,
            financial_year=financial_year,
            financial_month=financial_month
        ).first()

    # ------------------------------------------------------------------
    # Build the preview rows the grid will consume.
    # ------------------------------------------------------------------
    preview_rows = []
    row_errors = []
    skipped_rows = 0

    for row in parsed["rows"]:
        activity = EmissionActivity.objects.filter(
            id=row["activity_id"],
            is_active=True,
            allow_excel_import=True
        ).first()

        if not activity:
            row_errors.append(f"Activity ID {row['activity_id']} not found or not importable.")
            skipped_rows += 1
            continue

        source = None
        if row.get("source_id"):
            source = EmissionSource.objects.filter(
                id=row["source_id"],
                activity=activity,
                is_active=True
            ).first()
            if not source:
                row_errors.append(f"Source ID {row['source_id']} not found for activity {activity.name}.")
                skipped_rows += 1
                continue

        unit = Unit.objects.filter(id=row["unit_id"]).first()
        if not unit:
            row_errors.append(f"Unit ID {row['unit_id']} not found.")
            skipped_rows += 1
            continue

        factor = Decimal(str(row.get("factor", 0)))
        if activity.requires_emission_factor:
            factor_obj = EmissionFactor.objects.filter(
                activity=activity,
                is_active=True,
                effective_from__lte=timezone.now().date()
            ).order_by("-effective_from").first()
            if factor_obj:
                factor = factor_obj.emission_factor

        quantity = Decimal(str(row.get("quantity", 0)))
        total_emission = quantity * factor

        preview_rows.append({
            "category_id": row["category_id"],
            "activity_id": activity.id,
            "source_id": source.id if source else None,
            "unit_id": unit.id,
            "quantity": float(quantity),
            "factor": float(factor),
            "total": float(total_emission),
        })

    if not preview_rows:
        error_msg = "No valid rows could be imported."
        if row_errors:
            error_msg += " Errors: " + "; ".join(row_errors[:3])
        return JsonResponse(
            {"success": False, "message": error_msg},
            status=400
        )

    response_data = {
        "success": True,
        "message": (
            f"Parsed {len(preview_rows)} row(s) from Excel. "
            f"Review the grid below and click Save to store them."
        ),
        # --- COMPANY INFO ---
        "company_id": company.id,
        "company_name": company.company_name,
        # --- PLANT INFO ---
        "plant_id": plant.id,
        "plant_name": plant.name,
        # --- FINANCIAL YEAR INFO ---
        "financial_year_id": financial_year.id,
        "financial_year": str(financial_year.financial_year),
        # --- FINANCIAL MONTH INFO ---
        "financial_month_id": financial_month.id,
        "financial_month": financial_month.month_name,
        # --- SET DATA COLLECTION METHOD TO EXCEL ---
        "collection_method": "EXCEL",
        # --- FLAG TO INDICATE DATA IS FROM EXCEL (READ-ONLY) ---
        "is_imported_from_excel": True,
        # --- ROWS ---
        "rows": preview_rows,
        "errors": row_errors,
        "warnings": parsed.get("errors", []),
        "skipped_rows": skipped_rows,
    }

    if assignment:
        response_data["assignment_id"] = assignment.id

    logger.info(f"Upload successful: {len(preview_rows)} rows imported")
    return JsonResponse(response_data)