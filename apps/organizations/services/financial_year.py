from datetime import date

from django.db import transaction

from apps.organizations.models import FinancialYear


START_FINANCIAL_YEAR = 2023


@transaction.atomic
def ensure_current_financial_year(current_date=None):
    """
    Ensure that all Indian Financial Years from 2023-2024
    up to the current Financial Year exist in the database.

    Indian Financial Year:
        1 April -> 31 March
    """

    today = current_date or date.today()

    # Determine current Indian Financial Year
    if today.month >= 4:
        current_start_year = today.year
    else:
        current_start_year = today.year - 1

    current_financial_year = None
    created_any = False

    # Create all FYs from 2023-2024 to current FY
    for start_year in range(
        START_FINANCIAL_YEAR,
        current_start_year + 1
    ):
        end_year = start_year + 1

        # IMPORTANT:
        # FinancialYear model expects YYYY-YYYY
        financial_year_name = f"{start_year}-{end_year}"

        start_date = date(start_year, 4, 1)
        end_date = date(end_year, 3, 31)

        financial_year, created = FinancialYear.objects.get_or_create(
            financial_year=financial_year_name,
            defaults={
                "start_date": start_date,
                "end_date": end_date,
            }
        )

        if created:
            created_any = True

        # Store current FY
        if start_year == current_start_year:
            current_financial_year = financial_year

    return current_financial_year, created_any