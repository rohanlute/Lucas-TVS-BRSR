from datetime import date, datetime

from django.core.management.base import BaseCommand

from apps.emission.models import (
    EmissionAssignment,
    EmissionAssignmentSchedule,
)

from apps.emission.services import (
    due_schedules,
    run_daily_schedule_generation,
)


class Command(BaseCommand):
    help = "Test Emission Assignment Scheduler"

    def add_arguments(self, parser):

        parser.add_argument(
            "--date",
            type=str,
            required=True,
            help="Execution Date (YYYY-MM-DD)",
        )

        parser.add_argument(
            "--reset",
            action="store_true",
            help="Reset scheduler data before testing",
        )

    def handle(self, *args, **options):

        test_date = datetime.strptime(
            options["date"],
            "%Y-%m-%d",
        ).date()


        if options["reset"]:

            self.stdout.write("Resetting scheduler...")

            EmissionAssignment.objects.filter(
                schedule__isnull=False
            ).delete()

            for schedule in EmissionAssignmentSchedule.objects.all():

                schedule.last_run_date = None
                schedule.total_assignments_created = 0
                schedule.status = "ACTIVE"
                schedule.is_active = True
                schedule.next_run_date = schedule.start_date

                schedule.save(
                    update_fields=[
                        "last_run_date",
                        "total_assignments_created",
                        "status",
                        "is_active",
                        "next_run_date",
                    ]
                )

            self.stdout.write(
                self.style.SUCCESS("Reset completed.")
            )

        self.stdout.write("")
        self.stdout.write("=" * 60)
        self.stdout.write(" EMISSION SCHEDULER TEST ")
        self.stdout.write("=" * 60)
        self.stdout.write(f"Execution Date : {test_date}")
        self.stdout.write("")

        schedules = due_schedules(test_date)

        self.stdout.write(
            f"Schedules Due : {schedules.count()}"
        )
        self.stdout.write("")

        if not schedules.exists():
            self.stdout.write(
                self.style.WARNING(
                    "No schedules found."
                )
            )
            return

        self.stdout.write("-" * 60)

        for schedule in schedules:

            self.stdout.write(
                f"Schedule Code : {schedule.schedule_code}"
            )

            self.stdout.write(
                f"Name          : {schedule.name}"
            )

            self.stdout.write(
                f"Frequency     : {schedule.frequency}"
            )

            self.stdout.write(
                f"Next Run      : {schedule.next_run_date}"
            )

            self.stdout.write("-" * 60)

        created = run_daily_schedule_generation(
            test_date
        )

        self.stdout.write("")
        self.stdout.write("=" * 60)
        self.stdout.write(
            f"Assignments Created : {len(created)}"
        )
        self.stdout.write("=" * 60)

        if not created:

            self.stdout.write(
                self.style.WARNING(
                    "No assignments created."
                )
            )
            return

        for assignment in created:

            assignment.refresh_from_db()

            self.stdout.write("")
            self.stdout.write(
                self.style.SUCCESS(
                    f"Assignment : {assignment.assignment_code}"
                )
            )

            self.stdout.write(
                f"Schedule    : {assignment.schedule.schedule_code}"
                if assignment.schedule
                else "Schedule    : None"
            )

            self.stdout.write(
                f"Company     : {assignment.company}"
            )

            self.stdout.write(
                f"Plant       : {assignment.plant}"
            )

            self.stdout.write(
                f"Scope       : {assignment.scope}"
            )

            self.stdout.write(
                f"FY          : {assignment.financial_year}"
            )

            self.stdout.write(
                f"Month       : {assignment.financial_month}"
            )

            self.stdout.write(
                f"Status      : {assignment.status}"
            )

            self.stdout.write(
                f"Sources     : {assignment.assignment_sources.count()}"
            )

            self.stdout.write("-" * 60)

        self.stdout.write("")
        self.stdout.write("=" * 60)
        self.stdout.write("Schedule Status")
        self.stdout.write("=" * 60)

        for schedule in EmissionAssignmentSchedule.objects.order_by("id"):

            self.stdout.write("")
            self.stdout.write(
                f"{schedule.schedule_code}"
            )

            self.stdout.write(
                f"Last Run : {schedule.last_run_date}"
            )

            self.stdout.write(
                f"Next Run : {schedule.next_run_date}"
            )

            self.stdout.write(
                f"Total Generated : {schedule.total_assignments_created}"
            )

        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(
                "Scheduler Test Completed Successfully."
            )
        )