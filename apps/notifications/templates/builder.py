from .assignment_templates import AssignmentNotificationTemplates

from apps.common_events.constants import (
    EMISSION,
    ASSIGNMENT,
    ASSIGNED,
    SUBMITTED,
    REVIEW_APPROVED,
    REVIEW_REJECTED,
    FINAL_APPROVED,
    FINAL_REJECTED,
)


class NotificationTemplateBuilder:
    """
    Returns the appropriate notification template
    based on module, entity and action.
    """

    @classmethod
    def build(cls, context, recipient_type):

        assignment = context.target
        sender = context.actor

        # =====================================================
        # EMISSION ASSIGNMENT
        # =====================================================

        if (
            context.module == EMISSION
            and context.entity == ASSIGNMENT
        ):

            # -------------------------------------------------
            # ASSIGNED
            # -------------------------------------------------

            if context.action == ASSIGNED:

                if recipient_type == "assignee":

                    return (
                        AssignmentNotificationTemplates
                        .assigned_to_assignee(
                            assignment,
                            sender,
                        )
                    )

                if recipient_type == "reviewer":

                    return (
                        AssignmentNotificationTemplates
                        .assigned_to_reviewer(
                            assignment,
                            sender,
                        )
                    )

            # -------------------------------------------------
            # SUBMITTED
            # -------------------------------------------------

            elif context.action == SUBMITTED:

                if recipient_type == "reviewer_submit":

                    return (
                        AssignmentNotificationTemplates
                        .submitted_to_reviewer(
                            assignment,
                            sender,
                        )
                    )

            # -------------------------------------------------
            # REVIEW REJECTED
            # -------------------------------------------------

            elif context.action == REVIEW_REJECTED:

                if recipient_type == "assignee":

                    return (
                        AssignmentNotificationTemplates
                        .review_rejected(
                            assignment,
                            sender,
                        )
                    )

            # -------------------------------------------------
            # REVIEW APPROVED
            # -------------------------------------------------

            elif context.action == REVIEW_APPROVED:

                if recipient_type == "review_approved":

                    return (
                        AssignmentNotificationTemplates
                        .review_approved(
                            assignment,
                            sender,
                        )
                    )

            # -------------------------------------------------
            # FINAL APPROVED
            # -------------------------------------------------

            elif context.action == FINAL_APPROVED:

                if recipient_type == "final_approved":

                    return (
                        AssignmentNotificationTemplates
                        .final_approved(
                            assignment,
                            sender,
                        )
                    )

            # -------------------------------------------------
            # FINAL REJECTED
            # -------------------------------------------------

            elif context.action == FINAL_REJECTED:

                if recipient_type == "final_rejected":

                    return (
                        AssignmentNotificationTemplates
                        .final_rejected(
                            assignment,
                            sender,
                        )
                    )

        return None