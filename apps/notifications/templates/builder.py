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

        # -------------------------------------------------------
        # EMISSION
        # -------------------------------------------------------

        if (
            context.module == EMISSION
            and context.entity == ASSIGNMENT
        ):

            # ---------------------------------------------------
            # Assignment Created
            # ---------------------------------------------------

            if context.action == ASSIGNED:

                if recipient_type == "assignee":
                    return AssignmentNotificationTemplates.assigned_to_assignee(
                        assignment,
                        sender,
                    )

                if recipient_type == "reviewer":
                    return AssignmentNotificationTemplates.assigned_to_reviewer(
                        assignment,
                        sender,
                    )

            # ---------------------------------------------------
            # Assignment Submitted
            # ---------------------------------------------------

            elif context.action == SUBMITTED:

                if recipient_type == "reviewer_submit":
                    return AssignmentNotificationTemplates.submitted_to_reviewer(
                        assignment,
                        sender,
                    )

            # ---------------------------------------------------
            # Reviewer Approved
            # ---------------------------------------------------

            elif context.action == REVIEW_APPROVED:

                return AssignmentNotificationTemplates.review_approved(
                    assignment,
                    sender,
                )

            # ---------------------------------------------------
            # Reviewer Rejected
            # ---------------------------------------------------

            elif context.action == REVIEW_REJECTED:

                return AssignmentNotificationTemplates.review_rejected(
                    assignment,
                    sender,
                )

            # ---------------------------------------------------
            # Final Approved
            # ---------------------------------------------------

            elif context.action == FINAL_APPROVED:

                return AssignmentNotificationTemplates.final_approved(
                    assignment,
                    sender,
                )

            # ---------------------------------------------------
            # Final Rejected
            # ---------------------------------------------------

            elif context.action == FINAL_REJECTED:

                return AssignmentNotificationTemplates.final_rejected(
                    assignment,
                    sender,
                )

        return None