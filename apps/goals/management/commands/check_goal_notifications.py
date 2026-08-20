from django.core.management.base import BaseCommand

from apps.goals.models import KPI
from apps.goals.services.notification import GoalNotificationService
from apps.accounts.models import User


class Command(BaseCommand):

    help = "Check Goal KPIs and create meaningful notifications"

    def handle(self, *args, **options):

        self.stdout.write(
            self.style.NOTICE(
                "Starting Goal KPI notification check..."
            )
        )

        checked = 0
        notified = 0
        already_notified = 0
        skipped = 0
        errors = 0

        # ---------------------------------------------------------
        # Get active KPIs
        # ---------------------------------------------------------
        kpis = (
            KPI.objects
            .filter(
                is_active=True,
                goal__is_active=True,
                goal__material_topic__is_active=True,
            )
            .select_related(
                "goal",
                "goal__material_topic",
            )
        )

        for kpi in kpis:

            checked += 1

            try:

                # -------------------------------------------------
                # Get users who belong to the KPI's company
                # -------------------------------------------------
                recipients = (
                    User.objects
                    .filter(
                        is_active=True,
                        role__is_active=True,
                        company=kpi.goal.created_by.company,
                        role__permissions__code="ACCESS_GOAL_MODULE",
                        role__permissions__module_name="Goal",
                        role__permissions__permission_type="MODULE_ACCESS",
                    )
                    .distinct()
                )

                for recipient in recipients:

                    company = recipient.company

                    if not company:
                        skipped += 1
                        continue

                    result = GoalNotificationService.check_kpi(
                        kpi=kpi,
                        company=company,
                        recipient=recipient,
                    )

                    if result:

                        notification = result["notification"]
                        created = result["created"]

                        if created:
                            notified += 1

                            self.stdout.write(
                                self.style.SUCCESS(
                                    f"NEW notification: "
                                    f"{kpi.name} → "
                                    f"{notification.title} → "
                                    f"{recipient.username}"
                                )
                            )

                        else:
                            already_notified += 1

                            self.stdout.write(
                                f"Already notified: "
                                f"{kpi.name} → "
                                f"{notification.title} → "
                                f"{recipient.username}"
                            )

                    else:
                        skipped += 1

            except Exception as e:

                errors += 1

                self.stdout.write(
                    self.style.ERROR(
                        f"Error checking KPI "
                        f"'{kpi.name}': {e}"
                    )
                )

        # ---------------------------------------------------------
        # Summary
        # ---------------------------------------------------------
        self.stdout.write("")
        self.stdout.write(
            self.style.NOTICE(
                "Goal KPI notification check completed."
            )
        )

        self.stdout.write(
            f"KPIs checked: {checked}"
        )

        self.stdout.write(
            f"New notifications: {notified}"
        )

        self.stdout.write(
            f"Already notified: {already_notified}"
        )

        self.stdout.write(
            f"Skipped: {skipped}"
        )

        self.stdout.write(
            f"Errors: {errors}"
        )