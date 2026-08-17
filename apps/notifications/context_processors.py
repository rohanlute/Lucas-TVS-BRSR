from django.db import models

from .models import Timesheet, Notification


def global_notifications(request):
    """
    Add user-specific notifications and timesheets
    to all templates.
    """

    if request.user.is_authenticated:

        try:
            # =====================================================
            # TIMESHEETS
            # =====================================================
            # IMPORTANT:
            # A user should only see timesheets assigned to them.
            # Do NOT use assignment__assignee here because that
            # would expose reviewer/coordinator timesheets to
            # the original assignee.
            # =====================================================

            timesheets = (
                Timesheet.objects
                .filter(user=request.user)
                .select_related(
                    "assignment",
                    "company",
                    "user",
                )
                .order_by("-created_at")[:10]
            )

            # =====================================================
            # TIMESHEET COUNT
            # =====================================================

            timesheet_count = (
                Timesheet.objects
                .filter(
                    user=request.user,
                    status__in=[
                        "assigned",
                        "viewed",
                    ],
                )
                .count()
            )

            # =====================================================
            # NOTIFICATIONS
            # =====================================================

            navbar_notifications = (
                Notification.objects
                .filter(recipient=request.user)
                .exclude(title__icontains="Timesheet")
                .order_by("-created_at")[:10]
            )

            # =====================================================
            # UNREAD NOTIFICATION COUNT
            # =====================================================

            navbar_notification_count = (
                Notification.objects
                .filter(
                    recipient=request.user,
                    is_read=False,
                )
                .exclude(title__icontains="Timesheet")
                .count()
            )

            return {
                "timesheets": timesheets,
                "timesheet_count": timesheet_count,
                "navbar_notifications": navbar_notifications,
                "navbar_notification_count": navbar_notification_count,
            }

        except Exception as e:

            print(
                f"Error in global_notifications "
                f"context processor: {e}"
            )

    return {
        "timesheets": [],
        "timesheet_count": 0,
        "navbar_notifications": [],
        "navbar_notification_count": 0,
    }