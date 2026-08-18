import logging

from celery import shared_task

from .services import (
    run_daily_schedule_generation,
    run_daily_assignment_reminders,
)

logger = logging.getLogger(__name__)


# =====================================================
# Generate Scheduled Assignments
# =====================================================

@shared_task(
    name="emission.generate_scheduled_assignments"
)
def generate_scheduled_assignments():

    created = run_daily_schedule_generation()

    logger.info(
        "Generated %s scheduled assignments.",
        len(created),
    )

    return len(created)


# =====================================================
# Send Assignment Reminder Notifications
# =====================================================

@shared_task(
    name="emission.send_assignment_reminders"
)
def send_assignment_reminders():

    processed = run_daily_assignment_reminders()

    logger.info(
        "Processed %s emission assignments for reminders.",
        processed,
    )

    return processed