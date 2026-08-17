from datetime import date

from django.db import transaction

from apps.organizations.models import FinancialYear


@transaction.atomic
def ensure_current_financial_year(current_date=None):
    """
    Ensure that the current Indian Financial Year
    exists in the database.

    Indian Financial Year:
        1 April -> 31 March
    """

    today = current_date or date.today()
    

    # April to December
    if today.month >= 4:
        start_year = today.year

    # January to March
    else:
        start_year = today.year - 1

    end_year = start_year + 1

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

    return financial_year, created