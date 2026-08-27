from django.utils import timezone
from django.conf import settings
from apps.notifications.models import Notification
from apps.notifications.services import NotificationService
from apps.email_master.services import EmailService


class EmissionAssignmentReminderService:

    @classmethod
    def process_assignment(cls, assignment, today=None):
        """
        Check an assignment and create a due-date reminder
        for the appropriate users.
        """

        today = today or timezone.localdate()

        # -----------------------------------------
        # No due date
        # -----------------------------------------

        if not assignment.due_date:
            return

        # -----------------------------------------
        # Completed
        # -----------------------------------------

        if assignment.status == "APPROVED":
            return

        # -----------------------------------------
        # Calculate days remaining
        # -----------------------------------------

        days_remaining = (
            assignment.due_date - today
        ).days

        print("=" * 60)
        print("EMISSION ASSIGNMENT REMINDER CHECK")
        print("Assignment     :", assignment.assignment_code)
        print("Status         :", assignment.status)
        print("Due Date       :", assignment.due_date)
        print("Today          :", today)
        print("Days Remaining :", days_remaining)
        print("=" * 60)

        # -----------------------------------------
        # Only remind from 5 days before onward
        # -----------------------------------------

        if days_remaining > 5:
            return

        # -----------------------------------------
        # Determine recipients
        # -----------------------------------------

        recipients = cls.get_recipients(
            assignment=assignment,
            days_remaining=days_remaining,
        )

        # -----------------------------------------
        # Create notification
        # -----------------------------------------

        for recipient in recipients:

            cls.create_reminder_notification(
                assignment=assignment,
                recipient=recipient,
                days_remaining=days_remaining,
                today=today,
            )

    # =====================================================
    # RECIPIENT LOGIC
    # =====================================================

    @classmethod
    def get_recipients(
        cls,
        *,
        assignment,
        days_remaining,
    ):
        """
        Determine who should receive the reminder
        based on the current assignment status.
        """

        recipients = []

        # =================================================
        # ASSIGNEE DATA ENTRY
        # =================================================

        if assignment.status in [
            "ASSIGNED",
            "IN_PROGRESS",
        ]:

            # 5 days
            if days_remaining == 5:

                recipients = [
                    assignment.assignee,
                ]

            # 4 days
            elif days_remaining == 4:

                recipients = [
                    assignment.assignee,
                    assignment.reviewer,
                ]

            # 3, 2, 1, due date, overdue
            elif days_remaining <= 3:

                recipients = [
                    assignment.assignee,
                    assignment.reviewer,
                    assignment.assigner,
                ]

        # =================================================
        # REVIEW STAGE
        # =================================================

        elif assignment.status == "SUBMITTED":

            recipients = [
                assignment.reviewer,
                assignment.assigner,
            ]

        # =================================================
        # FINAL APPROVAL
        # =================================================

        elif assignment.status == "REVIEW_APPROVED":

            recipients = [
                assignment.assigner,
            ]

        # =================================================
        # REMOVE DUPLICATES
        # =================================================

        unique_recipients = []

        seen_ids = set()

        for user in recipients:

            if not user:
                continue

            if user.id in seen_ids:
                continue

            seen_ids.add(user.id)

            unique_recipients.append(user)

        return unique_recipients

    # =====================================================
    # CREATE REMINDER
    # =====================================================

    @classmethod
    def create_reminder_notification(
        cls,
        *,
        assignment,
        recipient,
        days_remaining,
        today=None,
    ):

        today = today or timezone.localdate()

        # -------------------------------------------------
        # Determine notification type
        # -------------------------------------------------

        if days_remaining < 0:

            notification_type = (
                Notification.NotificationTypeChoices.OVERDUE
            )

        else:

            notification_type = (
                Notification.NotificationTypeChoices.REMINDER
            )

        # -------------------------------------------------
        # Determine title based on workflow stage
        # -------------------------------------------------

        # =================================================
        # ASSIGNEE / DATA ENTRY STAGE
        # =================================================

        if assignment.status in [
            "ASSIGNED",
            "IN_PROGRESS",
        ]:

            if days_remaining > 1:

                title = (
                    f"{assignment.scope.name} Due in "
                    f"{days_remaining} Days"
                )

            elif days_remaining == 1:

                title = (
                    f"{assignment.scope.name} Due Tomorrow"
                )

            elif days_remaining == 0:

                title = (
                    f"{assignment.scope.name} Due Today"
                )

            else:

                overdue_days = abs(days_remaining)

                title = (
                    f"{assignment.scope.name} "
                    f"Assignment Overdue"
                )

        # =================================================
        # REVIEW STAGE
        # =================================================

        elif assignment.status == "SUBMITTED":

            if days_remaining > 1:

                title = (
                    f"{assignment.scope.name} "
                    f"Review Pending - Due in "
                    f"{days_remaining} Days"
                )

            elif days_remaining == 1:

                title = (
                    f"{assignment.scope.name} "
                    f"Review Pending - Due Tomorrow"
                )

            elif days_remaining == 0:

                title = (
                    f"{assignment.scope.name} "
                    f"Review Pending - Due Today"
                )

            else:

                title = (
                    f"{assignment.scope.name} "
                    f"Review Pending - Overdue"
                )

        # =================================================
        # FINAL APPROVAL STAGE
        # =================================================

        elif assignment.status == "REVIEW_APPROVED":

            if days_remaining > 1:

                title = (
                    f"{assignment.scope.name} "
                    f"Final Approval Pending - Due in "
                    f"{days_remaining} Days"
                )

            elif days_remaining == 1:

                title = (
                    f"{assignment.scope.name} "
                    f"Final Approval Pending - Due Tomorrow"
                )

            elif days_remaining == 0:

                title = (
                    f"{assignment.scope.name} "
                    f"Final Approval Pending - Due Today"
                )

            else:

                title = (
                    f"{assignment.scope.name} "
                    f"Final Approval Pending - Overdue"
                )

        # =================================================
        # FALLBACK
        # =================================================

        else:

            if days_remaining > 1:

                title = (
                    f"{assignment.scope.name} "
                    f"Action Pending - Due in "
                    f"{days_remaining} Days"
                )

            elif days_remaining == 1:

                title = (
                    f"{assignment.scope.name} "
                    f"Action Pending - Due Tomorrow"
                )

            elif days_remaining == 0:

                title = (
                    f"{assignment.scope.name} "
                    f"Action Pending - Due Today"
                )

            else:

                title = (
                    f"{assignment.scope.name} "
                    f"Action Pending - Overdue"
                )

        # -------------------------------------------------
        # Determine message
        # -------------------------------------------------

        if days_remaining > 0:

            message = (
                f"{assignment.plant.name} • "
                f"{assignment.scope.name}\n\n"
                f"Assignment: "
                f"{assignment.assignment_code}\n"
                f"Due Date: "
                f"{assignment.due_date.strftime('%d-%b-%Y')}\n\n"
                f"{cls.get_pending_message(assignment)}"
            )

        elif days_remaining == 0:

            message = (
                f"{assignment.plant.name} • "
                f"{assignment.scope.name}\n\n"
                f"Assignment: "
                f"{assignment.assignment_code}\n"
                f"Due Date: "
                f"{assignment.due_date.strftime('%d-%b-%Y')}\n\n"
                f"{cls.get_pending_message(assignment)}"
            )

        else:

            overdue_days = abs(days_remaining)

            message = (
                f"{assignment.plant.name} • "
                f"{assignment.scope.name}\n\n"
                f"Assignment: "
                f"{assignment.assignment_code}\n"
                f"Due Date: "
                f"{assignment.due_date.strftime('%d-%b-%Y')}\n"
                f"Overdue By: "
                f"{overdue_days} day(s)\n\n"
                f"{cls.get_pending_message(assignment)}"
            )

        # -------------------------------------------------
        # Duplicate protection
        # -------------------------------------------------

        if (
            notification_type
            == Notification.NotificationTypeChoices.OVERDUE
        ):

            # ---------------------------------------------
            # Overdue:
            # One notification per recipient per day.
            # ---------------------------------------------

            already_sent = Notification.objects.filter(
                company=assignment.company,
                recipient=recipient,
                module=Notification.ModuleChoices.EMISSION,
                notification_type=notification_type,
                reference_id=assignment.id,
                created_at__date=today,
            ).exists()

        else:

            # ---------------------------------------------
            # Reminder:
            # Each workflow stage + reminder period is
            # treated as a separate notification.
            #
            # Example:
            #
            # Scope 3 Due in 5 Days
            # Scope 3 Due in 4 Days
            # Scope 3 Due in 3 Days
            #
            # Reviewer:
            #
            # Scope 3 Review Pending - Due in 3 Days
            #
            # ESG Coordinator:
            #
            # Scope 3 Final Approval Pending - Due in 3 Days
            # ---------------------------------------------

            already_sent = Notification.objects.filter(
                company=assignment.company,
                recipient=recipient,
                module=Notification.ModuleChoices.EMISSION,
                notification_type=notification_type,
                reference_id=assignment.id,
                title=title,
            ).exists()

        # -------------------------------------------------
        # Stop duplicate
        # -------------------------------------------------

        if already_sent:

            print(
                f"Reminder already sent for "
                f"{assignment.assignment_code} "
                f"to {recipient.username}: "
                f"{title}"
            )

            return

        # -------------------------------------------------
        # Create notification
        # -------------------------------------------------

        notification = NotificationService.create(

            company=assignment.company,

            sender=assignment.assigner,

            recipient=recipient,

            module=Notification.ModuleChoices.EMISSION,

            notification_type=notification_type,

            title=title,

            message=message,

            reference_id=assignment.id,

            action_url=(
                f"/emission/assignment/"
                f"{assignment.id}/"
            ),
        )


        # -------------------------------------------------
        # Send the same reminder by email
        # -------------------------------------------------

        assignment_url = (f"{settings.SITE_URL.rstrip('/')}"
            f"/emission/assignments/{assignment.id}/"
        )

        email_sent = EmailService.send_email(
            recipient=recipient,
            subject=title,
            message=message,
            html_template="emails/emission/assignment_reminder.html",
            context={
                "assignment": assignment,
                "recipient": recipient,
                "assignment_url": assignment_url,
                "days_remaining": days_remaining,
                "is_overdue": days_remaining < 0,
            },
        )

        if email_sent:

            print(
                f"✅ REMINDER email sent: "
                f"{assignment.assignment_code} → "
                f"{recipient.username} | {title}"
            )

        else:

            print(
                f"❌ REMINDER email failed: "
                f"{assignment.assignment_code} → "
                f"{recipient.username} | {title}"
            )

        print(
            f"✅ {notification_type} notification created: "
            f"{assignment.assignment_code} → "
            f"{recipient.username} | {title}"
        )

    # =====================================================
    # PENDING MESSAGE
    # =====================================================

    @classmethod
    def get_pending_message(cls, assignment):

        if assignment.status in [
            "ASSIGNED",
            "IN_PROGRESS",
        ]:

            return (
                "Data collection is still pending. "
                "Please complete the assigned activity."
            )

        elif assignment.status == "SUBMITTED":

            return (
                "The data has been submitted and is "
                "waiting for reviewer action."
            )

        elif assignment.status == "REVIEW_APPROVED":

            return (
                "Reviewer approval is complete. "
                "Final approval is pending."
            )

        return (
            "Please take the required action on this assignment."
        )