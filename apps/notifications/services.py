import logging
from .models import Notification, Timesheet
logger = logging.getLogger(__name__)


class NotificationService:

    EVENTS = {
        "ASSIGN_SCOPE": "_assign_scope",
        "SUBMIT_SCOPE": "_submit_scope",
        "APPROVE_SCOPE": "_approve_scope",
        "REJECT_SCOPE": "_reject_scope",
        "GOAL_CREATED": "_goal_created",
    }

    @classmethod
    def notify(cls, event, **kwargs):

        handler = cls.EVENTS.get(event)

        if not handler:
            raise ValueError(f"Unknown notification event: {event}")

        return getattr(cls, handler)(**kwargs)


     # -------------------------------------------------------
    # Generic Notification Creator
    # -------------------------------------------------------

    @classmethod
    def create(
        cls,
        *,
        company,
        sender,
        recipient,
        module,
        notification_type,
        title,
        message,
        reference_id=None,
        action_url="",
    ):
        """
        Generic notification creator.

        Used by the Common Event Framework.

        Existing notify() methods continue to work unchanged.
        """

        return Notification.objects.create(

            company=company,

            sender=sender,

            recipient=recipient,

            module=module,

            notification_type=notification_type,

            title=title,

            message=message,

            reference_id=reference_id,

            action_url=action_url,

        )

    
    # -------------------------------------------------------
    # Scope Assigned
    # -------------------------------------------------------

    @classmethod
    def _assign_scope(cls, assignment, sender):

        return Notification.objects.create(
            company=assignment.company,
            sender=sender,
            recipient=assignment.assignee,
            module=Notification.ModuleChoices.EMISSION,
            notification_type=Notification.NotificationTypeChoices.ASSIGNED,
            title=f"{assignment.scope.name} Data Entry Assigned",

            message=(
                f"{assignment.plant.name} • "
                f"{assignment.financial_month.month_name} "
                f"{assignment.financial_year.financial_year}"
            ),
            reference_id=assignment.id,
            action_url=f"/emission/assignment/{assignment.id}/",
        )

    # -------------------------------------------------------
    # Scope Submitted
    # -------------------------------------------------------

    @classmethod
    def _submit_scope(cls, assignment, sender):

        return Notification.objects.create(
            company=assignment.company,
            sender=sender,
            recipient=assignment.assigner,
            module=Notification.ModuleChoices.EMISSION,
            notification_type=Notification.NotificationTypeChoices.SUBMITTED,
            title=f"{assignment.scope.name} Submitted",
            message=(
                f"{assignment.plant.name} • "
                f"{assignment.financial_month.month_name} "
                f"{assignment.financial_year.financial_year}"
            ),
            reference_id=assignment.id,
            action_url=f"/emission/assignment/{assignment.id}/",
        )

    # -------------------------------------------------------
    # Scope Approved
    # -------------------------------------------------------

    @classmethod
    def _approve_scope(cls, assignment, sender):

        return Notification.objects.create(
            company=assignment.company,
            sender=sender,
            recipient=assignment.assignee,
            module=Notification.ModuleChoices.EMISSION,
            notification_type=Notification.NotificationTypeChoices.APPROVED,
            title=f"{assignment.scope.name} Approved",
            message=(
                f"{assignment.plant.name} • "
                f"{assignment.financial_month.month_name} "
                f"{assignment.financial_year.financial_year}"
            ),
            reference_id=assignment.id,
            action_url=f"/emission/assignment/{assignment.id}/",
        )

    # -------------------------------------------------------
    # Scope Rejected
    # -------------------------------------------------------

    @classmethod
    def _reject_scope(cls, assignment, sender, comments=""):

        return Notification.objects.create(
            company=assignment.company,
            sender=sender,
            recipient=assignment.assignee,
            module=Notification.ModuleChoices.EMISSION,
            notification_type=Notification.NotificationTypeChoices.REJECTED,
            title=f"{assignment.scope.name} Rejected",
            message=(
                f"{assignment.plant.name} • "
                f"{assignment.financial_month.month_name} "
                f"{assignment.financial_year.financial_year}"
            ),
            reference_id=assignment.id,
            action_url=f"/emission/assignment/{assignment.id}/",
        )

    @classmethod
    def _goal_created(cls, goal, sender):

        from django.contrib.auth import get_user_model
        from django.urls import reverse

        User = get_user_model()

        # -------------------------------------------------------
        # Find all active users who have permission
        # to access/view the Goal module.
        #
        # Actual permission:
        # code = ACCESS_GOAL_MODULE
        # module_name = Goal
        # permission_type = MODULE_ACCESS
        # -------------------------------------------------------
        recipients = (
            User.objects
            .filter(
                is_active=True,
                role__is_active=True,
                company=sender.company,
                role__permissions__code="ACCESS_GOAL_MODULE",
                role__permissions__module_name="Goal",
                role__permissions__permission_type="MODULE_ACCESS",
            )
            .distinct()
        )

        action_url = reverse(
            "goals:goal_detail",
            kwargs={
                "material_topic": goal.material_topic.name
            }
        )

        action_url = f"{action_url}?goal={goal.name}"

        notifications = []

        for recipient in recipients:

            company = getattr(recipient, "company", None)

            # Notification.company is mandatory
            if not company:
                logger.warning(
                    f"Skipping Goal notification for user "
                    f"{recipient.id}: no company assigned."
                )
                continue

            notification = cls.create(
                company=company,
                sender=sender,
                recipient=recipient,
                module=Notification.ModuleChoices.GOALS,
                notification_type=Notification.NotificationTypeChoices.CREATED,
                title=f'New Goal Created "{goal.name}"',
                message=(
                    f'New goal "{goal.name}" has been created '
                    f'under "{goal.material_topic.name}".'
                ),
                reference_id=goal.id,
                action_url=action_url,
            )

            notifications.append(notification)

        logger.info(
            f"Created {len(notifications)} notification(s) "
            f"for newly created Goal '{goal.name}'."
        )

        return notifications



    
# ===================================================================
# Generic Timesheet Service
# ===================================================================

class TimesheetService:

    @classmethod
    def create(
        cls,
        *,
        user,
        assignment,
        company,
        title,
        description,
        start_date,
        end_date,
        status="assigned",
        hours_worked=0,
        notification=None,
    ):

        return Timesheet.objects.create(
            user=user,
            assignment=assignment,
            company=company,
            title=title,
            description=description,
            start_date=start_date,
            end_date=end_date,
            status=status,
            hours_worked=hours_worked,
            notification=notification,
        )

    @classmethod
    def exists_for_user(cls, assignment, user):

        return Timesheet.objects.filter(
            assignment=assignment,
            user=user,
        ).exists()

    @classmethod
    def get_by_assignment(cls, assignment):

        return Timesheet.objects.filter(
            assignment=assignment
        ).first()

    @classmethod
    def exists(cls, assignment):

        return Timesheet.objects.filter(
            assignment=assignment
        ).exists()

    @classmethod
    def update(cls, timesheet, **kwargs):

        for key, value in kwargs.items():
            setattr(timesheet, key, value)

        timesheet.save()

        return timesheet