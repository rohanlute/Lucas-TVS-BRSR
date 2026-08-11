"""
Automatic Emission Assignment Scheduler

This module is responsible for:

1. Finding schedules due today.
2. Creating Emission Assignments.
3. Starting workflow.
4. Sending notifications.
5. Calculating next run date.
"""

from datetime import timedelta
import logging

from django.utils import timezone
from .assignment_service import create_emission_assignment
from .models import EmissionAssignment, EmissionAssignmentSchedule

from apps.organizations.models import (
    FinancialYear,
    FinancialMonth,
)
from .schedule_utils import calculate_next_run_date


logger = logging.getLogger(__name__)

def get_financial_year(today):
    """
    Returns the FinancialYear object for a given date.
    """

    return FinancialYear.objects.get(
        start_date__lte=today,
        end_date__gte=today,
    )


def get_financial_month(today):
    """
    Converts calendar month into FinancialMonth.
    """

    mapping = {
        4: 1,   # April
        5: 2,
        6: 3,
        7: 4,
        8: 5,
        9: 6,
        10: 7,
        11: 8,
        12: 9,
        1: 10,
        2: 11,
        3: 12,
    }

    return FinancialMonth.objects.get(
        month_number=mapping[today.month]
    )


def due_schedules(today=None):
    """
    Returns all active schedules due today.
    """

    today = today or timezone.localdate()

    return (
        EmissionAssignmentSchedule.objects
        .filter(
            status="ACTIVE",
            is_active=True,
            next_run_date=today,
        )
        .select_related(
            "company",
            "plant",
            "scope",
            "assigner",
            "assignee",
            "reviewer",
            "workflow_template",
        )
    )




def run_daily_schedule_generation(today=None):

    today = today or timezone.localdate()

    financial_year = get_financial_year(today)

    financial_month = get_financial_month(today)

    schedules = due_schedules(today)

    created = []

    for schedule in schedules:

        # ----------------------------------------
        # Stop Schedule After End Date
        # ----------------------------------------

        if schedule.end_date and today > schedule.end_date:

            schedule.status = "COMPLETED"

            schedule.is_active = False

            schedule.next_run_date = None

            schedule.save(
                update_fields=[
                    "status",
                    "is_active",
                    "next_run_date",
                ]
            )

            logger.info(
                "Schedule %s completed.",
                schedule.schedule_code,
            )

            continue

        source_ids = list(
            schedule.schedule_sources.values_list(
                "source_id",
                flat=True,
            )
        )

        # ----------------------------------------
        # Prevent Duplicate Assignment
        # ----------------------------------------

        exists = EmissionAssignment.objects.filter(
            schedule=schedule,
            financial_year=financial_year,
            financial_month=financial_month,
        ).exists()

        if exists:
            logger.info(
                "Assignment already exists for schedule %s",
                schedule.schedule_code,
            )
            continue

        print("=" * 60)
        print("Creating assignment for:", schedule.schedule_code)
        print("Source IDs:", source_ids)
        print("Financial Year:", financial_year)
        print("Financial Month:", financial_month)

        try:

            assignment = create_emission_assignment(

                company_id=schedule.company_id,

                plant_id=schedule.plant_id,

                financial_year_id=financial_year.id,

                financial_month_id=financial_month.id,

                scope_id=schedule.scope_id,

                schedule=schedule,

                assignee=schedule.assignee,

                assigner=schedule.assigner,

                reviewer=schedule.reviewer,

                due_date=schedule.end_date,

                priority=schedule.priority,

                notes=schedule.notes,

                source_ids=source_ids,
            )

            print("Returned Assignment:", assignment)

            if assignment:
                created.append(assignment)
                print("Created Count:", len(created))
            else:
                print("Returned None")

        except Exception as e:

            print("=" * 60)
            print("ERROR CREATING ASSIGNMENT")
            print(type(e).__name__)
            print(str(e))
            print("=" * 60)

            raise

        print("Checking Duplicate...")

        exists = EmissionAssignment.objects.filter(
            schedule=schedule,
            financial_year=financial_year,
            financial_month=financial_month,
        ).exists()

        print("Duplicate Exists:", exists)

        # ----------------------------------------
        # Complete One Time Schedule
        # ----------------------------------------

        if schedule.schedule_type == "ONE_TIME":

            schedule.status = "COMPLETED"

            schedule.is_active = False

            schedule.next_run_date = None

            schedule.last_run_date = today

            schedule.total_assignments_created += 1

            schedule.save(
                update_fields=[
                    "status",
                    "is_active",
                    "next_run_date",
                    "last_run_date",
                    "total_assignments_created",
                ]
            )

            continue

        schedule.last_run_date = today

        schedule.total_assignments_created += 1

        next_date = calculate_next_run_date(
            schedule,
            today,
        )

        print("===================================")
        print("Schedule :", schedule.schedule_code)
        print("Frequency:", schedule.frequency)
        print("Type     :", schedule.schedule_type)
        print("Months   :", schedule.selected_months)
        print("Today    :", today)
        print("Next Date:", next_date)
        print("===================================")

        schedule.next_run_date = next_date

        schedule.save(
            update_fields=[
                "last_run_date",
                "next_run_date",
                "total_assignments_created",
            ]
        )


        schedule.save(
            update_fields=[
                "last_run_date",
                "next_run_date",
                "total_assignments_created",
            ]
        )

    return created