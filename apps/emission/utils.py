from .models import (
    EmissionAssignment,
    EmissionAssignmentSchedule,
)


def generate_assignment_code():

    last = (
        EmissionAssignment.objects
        .order_by("-id")
        .first()
    )

    if not last:
        return "EA000001"

    number = int(last.assignment_code[2:]) + 1

    return f"EA{number:06d}"


def generate_schedule_code():

    last = (
        EmissionAssignmentSchedule.objects
        .order_by("-id")
        .first()
    )

    if not last:
        return "ES000001"

    number = int(last.schedule_code[2:]) + 1

    return f"ES{number:06d}"