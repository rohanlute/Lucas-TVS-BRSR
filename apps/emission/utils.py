from django.utils import timezone

from .models import (
    EmissionAssignment,
    EmissionAssignmentSchedule,
)


def generate_assignment_code():
    """
    Generate assignment code in the format:

    EMISSION-2026-0001
    EMISSION-2026-0002
    EMISSION-2026-0003
    """

    current_year = timezone.now().year
    prefix = f"EMISSION-{current_year}-"

    last = (
        EmissionAssignment.objects
        .filter(
            assignment_code__startswith=prefix
        )
        .order_by("-id")
        .first()
    )

    if not last:
        return f"{prefix}0001"

    try:
        last_number = int(
            last.assignment_code.rsplit("-", 1)[-1]
        )
    except (ValueError, IndexError):
        last_number = 0

    return f"{prefix}{last_number + 1:04d}"


def generate_schedule_code():
    """
    Generate schedule code in the format:

    EMISSION-SCH-2026-0001
    EMISSION-SCH-2026-0002
    EMISSION-SCH-2026-0003
    """

    current_year = timezone.now().year
    prefix = f"EMISSION-SCH-{current_year}-"

    last = (
        EmissionAssignmentSchedule.objects
        .filter(
            schedule_code__startswith=prefix
        )
        .order_by("-id")
        .first()
    )

    if not last:
        return f"{prefix}0001"

    try:
        last_number = int(
            last.schedule_code.rsplit("-", 1)[-1]
        )
    except (ValueError, IndexError):
        last_number = 0

    return f"{prefix}{last_number + 1:04d}"