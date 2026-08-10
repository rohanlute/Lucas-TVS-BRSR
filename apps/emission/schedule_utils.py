from datetime import date

from dateutil.relativedelta import relativedelta


# =====================================================
# Financial Month Mapping
# =====================================================

# Financial Month -> Calendar Month
# 1=April ... 12=March

FINANCIAL_TO_CALENDAR = {
    1: 4,
    2: 5,
    3: 6,
    4: 7,
    5: 8,
    6: 9,
    7: 10,
    8: 11,
    9: 12,
    10: 1,
    11: 2,
    12: 3,
}

# Calendar Month -> Financial Month
CALENDAR_TO_FINANCIAL = {
    value: key
    for key, value in FINANCIAL_TO_CALENDAR.items()
}


# =====================================================
# Next Run Date
# =====================================================

def calculate_next_run_date(schedule, current_date):
    """
    Calculate the next execution date for a schedule.

    Supports:
    - One Time
    - Monthly (Selected Months)
    - Quarterly
    - Half Yearly
    - Yearly
    """

    # -------------------------------------------------
    # One Time
    # -------------------------------------------------

    if schedule.schedule_type == "ONE_TIME":
        return None

    # -------------------------------------------------
    # Monthly
    # -------------------------------------------------

    if schedule.frequency == "MONTHLY":

        selected = sorted(schedule.selected_months or [])

        # If no months configured, simply go next month
        if not selected:
            return current_date + relativedelta(months=1)

        current_financial = CALENDAR_TO_FINANCIAL[current_date.month]

        # Find next configured financial month
        for month_no in selected:

            if month_no > current_financial:

                calendar_month = FINANCIAL_TO_CALENDAR[month_no]

                year = current_date.year

                # Crossed calendar year
                if calendar_month < current_date.month:
                    year += 1

                return date(year, calendar_month, 1)

        # Wrap to first configured month
        first_month = selected[0]

        calendar_month = FINANCIAL_TO_CALENDAR[first_month]

        year = current_date.year

        if calendar_month <= current_date.month:
            year += 1

        return date(year, calendar_month, 1)

    # -------------------------------------------------
    # Quarterly
    # -------------------------------------------------

    if schedule.frequency == "QUARTERLY":
        return current_date + relativedelta(months=3)

    # -------------------------------------------------
    # Half Yearly
    # -------------------------------------------------

    if schedule.frequency == "HALF_YEARLY":
        return current_date + relativedelta(months=6)

    # -------------------------------------------------
    # Yearly
    # -------------------------------------------------

    if schedule.frequency == "YEARLY":
        return current_date + relativedelta(years=1)

    return None