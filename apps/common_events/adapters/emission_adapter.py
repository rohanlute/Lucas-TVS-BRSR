from apps.common_events.constants import ASSIGNED, SUBMITTED
from apps.notifications.templates.builder import NotificationTemplateBuilder


class EmissionAdapter:
    """
    Converts Emission objects into common event data.
    """

    # =====================================================
    # Notification Builder
    # =====================================================

    @classmethod
    def build_notification(cls, context):

        assignment = context.target

        notifications = []

        # -------------------------------------------------------
        # Assignment Created
        # -------------------------------------------------------

        if context.action == ASSIGNED:

            assignee_template = NotificationTemplateBuilder.build(
                context,
                recipient_type="assignee",
            )

            notifications.append({

                "company": assignment.company,

                "sender": context.actor,

                "recipient": assignment.assignee,

                "module": "EMISSION",

                "notification_type": "ASSIGNED",

                "title": assignee_template["title"],

                "message": assignee_template["message"],

                "reference_id": assignment.id,

                "action_url": f"/emission/assignments/{assignment.id}/",

            })

            if assignment.reviewer:

                reviewer_template = NotificationTemplateBuilder.build(
                    context,
                    recipient_type="reviewer",
                )

                notifications.append({

                    "company": assignment.company,

                    "sender": context.actor,

                    "recipient": assignment.reviewer,

                    "module": "EMISSION",

                    "notification_type": "ASSIGNED",

                    "title": reviewer_template["title"],

                    "message": reviewer_template["message"],

                    "reference_id": assignment.id,

                    "action_url": f"/emission/assignments/{assignment.id}/",

                })

        # -------------------------------------------------------
        # Assignment Submitted
        # -------------------------------------------------------

        elif context.action == SUBMITTED:

            if assignment.reviewer:

                reviewer_template = NotificationTemplateBuilder.build(
                    context,
                    recipient_type="reviewer_submit",
                )

                notifications.append({

                    "company": assignment.company,

                    "sender": context.actor,

                    "recipient": assignment.reviewer,

                    "module": "EMISSION",

                    "notification_type": "SUBMITTED",

                    "title": reviewer_template["title"],

                    "message": reviewer_template["message"],

                    "reference_id": assignment.id,

                    "action_url": f"/emission/assignments/{assignment.id}/",

                })

        return notifications

    # =====================================================
    # Timesheet Builder
    # =====================================================

    @classmethod
    def build_timesheet(cls, context):

        assignment = context.target

        # -------------------------------------------------------
        # Assignment Created
        # -------------------------------------------------------

        if context.action == ASSIGNED:

            return {

                "user": assignment.assignee,

                "assignment": assignment,

                "company": assignment.company,

                "title": f"Timesheet: {assignment.scope.name}",

                "description": (
                    f"Data Collection - {assignment.scope.name}"
                ),

                "start_date": assignment.created_at,

                "end_date": assignment.due_date,

                "status": "assigned",

                "hours_worked": 0,

                "notification": None,

            }

        # -------------------------------------------------------
        # Assignment Submitted
        # -------------------------------------------------------

        elif context.action == SUBMITTED:

            if not assignment.reviewer:
                return None

            return {

                "user": assignment.reviewer,

                "assignment": assignment,

                "company": assignment.company,

                "title": f"Review: {assignment.scope.name}",

                "description": (
                    f"Review submitted data for "
                    f"{assignment.scope.name}"
                ),

                "start_date": assignment.created_at,

                "end_date": assignment.due_date,

                "status": "assigned",

                "hours_worked": 0,

                "notification": None,

            }

        return None

    # =====================================================
    # Email Builder
    # =====================================================

    @classmethod
    def build_email(cls, context):
        return None

    # =====================================================
    # Audit Builder
    # =====================================================

    @classmethod
    def build_audit(cls, context):
        return None