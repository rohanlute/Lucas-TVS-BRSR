from .models import Notification,Timesheet


class NotificationService:

    EVENTS = {
        "ASSIGN_SCOPE": "_assign_scope",
        "SUBMIT_SCOPE": "_submit_scope",
        "APPROVE_SCOPE": "_approve_scope",
        "REJECT_SCOPE": "_reject_scope",
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