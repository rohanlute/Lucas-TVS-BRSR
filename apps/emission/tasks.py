import logging

from celery import shared_task

from .services import run_daily_schedule_generation

logger = logging.getLogger(__name__)


@shared_task(name="emission.generate_scheduled_assignments")
def generate_scheduled_assignments():

    created = run_daily_schedule_generation()

    logger.info(
        "Generated %s scheduled assignments.",
        len(created),
    )

    return len(created)