from .models import Notification


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