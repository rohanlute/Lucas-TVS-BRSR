from datetime import date

from dateutil.relativedelta import relativedelta


# =====================================================
# Financial Month Mapping
# =====================================================

# Financial Month -> Calendar Month
# 1 = April ... 12 = March

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

# =====================================================
# Quarter Mapping
# =====================================================

QUARTER_TO_FINANCIAL_MONTH = {
    "Q1": 1,    # April
    "Q2": 4,    # July
    "Q3": 7,    # October
    "Q4": 10,   # January
}



# Calendar Month -> Financial Month

CALENDAR_TO_FINANCIAL = {
    value: key
    for key, value in FINANCIAL_TO_CALENDAR.items()
}


def get_next_financial_month(current_financial_month, allowed_months):
    """
    Returns:
        (financial_month, wrapped)

    wrapped=True means the next month is in the next financial year.
    """

    allowed_months = sorted(allowed_months)

    for month in allowed_months:
        if month > current_financial_month:
            return month, False

    return allowed_months[0], True



def financial_month_to_date(financial_month, current_date, wrapped=False):
    """
    Converts a financial month (1=Apr ... 12=Mar)
    into the correct calendar date.
    """

    calendar_month = FINANCIAL_TO_CALENDAR[financial_month]

    year = current_date.year

    # January, February and March belong to the next
    # calendar year when moving forward in the same FY.
    if calendar_month in (1, 2, 3):
        if current_date.month >= 4:
            year += 1

    # Wrapped means next financial cycle
    if wrapped:
        year += 1

    return date(year, calendar_month, 1)





# =====================================================
# Monthly
# =====================================================

def calculate_monthly_next_run(schedule, current_date):

    selected = schedule.selected_months or []

    if not selected:
        return current_date + relativedelta(months=1)

    current = CALENDAR_TO_FINANCIAL[current_date.month]

    next_month, wrapped = get_next_financial_month(
        current,
        selected,
    )

    return financial_month_to_date(
        next_month,
        current_date,
        wrapped,
    )

# =====================================================
# Quarterly
# =====================================================

QUARTER_STARTS = {
    "Q1": (4, 1),     # April  -> Financial Month 1
    "Q2": (7, 4),     # July   -> Financial Month 4
    "Q3": (10, 7),    # October-> Financial Month 7
    "Q4": (1, 10),    # January-> Financial Month 10
}


def current_quarter(current_date):
    month = current_date.month

    if month in (4, 5, 6):
        return "Q1"

    if month in (7, 8, 9):
        return "Q2"

    if month in (10, 11, 12):
        return "Q3"

    return "Q4"

def calculate_quarterly_next_run(schedule, current_date):

    selected = schedule.selected_quarters or []

    if not selected:
        return current_date + relativedelta(months=3)

    quarter_months = {
        "Q1": 1,     # April
        "Q2": 4,     # July
        "Q3": 7,     # October
        "Q4": 10,    # January
    }

    allowed_months = sorted(
        quarter_months[q]
        for q in selected
    )

    current = CALENDAR_TO_FINANCIAL[current_date.month]

    next_month, wrapped = get_next_financial_month(
        current,
        allowed_months,
    )

    return financial_month_to_date(
        next_month,
        current_date,
        wrapped,
    )


# =====================================================
# Half Yearly
# =====================================================

def calculate_half_yearly_next_run(schedule, current_date):

    selected = schedule.selected_months or []

    if not selected:
        return current_date + relativedelta(months=6)

    current = CALENDAR_TO_FINANCIAL[current_date.month]

    next_month, wrapped = get_next_financial_month(
        current,
        selected,
    )

    return financial_month_to_date(
        next_month,
        current_date,
        wrapped,
    )


# =====================================================
# Yearly
# =====================================================

def calculate_yearly_next_run(schedule, current_date):

    return current_date + relativedelta(years=1)


# =====================================================
# Dispatcher
# =====================================================

def calculate_next_run_date(schedule, current_date):
    """
    Returns the next execution date for the schedule.
    """

    if schedule.schedule_type == "ONE_TIME":
        return None

    if schedule.frequency == "MONTHLY":
        return calculate_monthly_next_run(
            schedule,
            current_date,
        )

    if schedule.frequency == "QUARTERLY":
        return calculate_quarterly_next_run(
            schedule,
            current_date,
        )

    if schedule.frequency == "HALF_YEARLY":
        return calculate_half_yearly_next_run(
            schedule,
            current_date,
        )

    if schedule.frequency == "YEARLY":
        return calculate_yearly_next_run(
            schedule,
            current_date,
        )

    return None