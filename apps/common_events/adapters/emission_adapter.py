from django.conf import settings
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

from apps.notifications.templates.builder import (
    NotificationTemplateBuilder,
)


class EmissionAdapter:
    """
    Converts Emission events into notification
    and timesheet data.
    """

    # =====================================================
    # NOTIFICATIONS
    # =====================================================

    @classmethod
    def build_notification(cls, context):

        assignment = context.target

        notifications = []

        # =================================================
        # 1. ASSIGNED
        # Assignee gets notification
        # Reviewer gets notification
        # =================================================

        if context.action == ASSIGNED:

            # -----------------------------
            # Assignee
            # -----------------------------

            if assignment.assignee:

                template = NotificationTemplateBuilder.build(
                    context,
                    recipient_type="assignee",
                )

                if template:

                    notifications.append({
                        "company": assignment.company,
                        "sender": context.actor,
                        "recipient": assignment.assignee,
                        "module": EMISSION,
                        "notification_type": "ASSIGNED",
                        "title": template["title"],
                        "message": template["message"],
                        "reference_id": assignment.id,
                        "action_url": (
                            f"/emission/assignments/"
                            f"{assignment.id}/"
                        ),
                    })

            # -----------------------------
            # Reviewer
            # -----------------------------

            if assignment.reviewer:

                template = NotificationTemplateBuilder.build(
                    context,
                    recipient_type="reviewer",
                )

                if template:

                    notifications.append({
                        "company": assignment.company,
                        "sender": context.actor,
                        "recipient": assignment.reviewer,
                        "module": EMISSION,
                        "notification_type": "ASSIGNED",
                        "title": template["title"],
                        "message": template["message"],
                        "reference_id": assignment.id,
                        "action_url": (
                            f"/emission/assignments/"
                            f"{assignment.id}/"
                        ),
                    })

        # =================================================
        # 2. SUBMITTED
        # Reviewer gets notification
        # =================================================

        elif context.action == SUBMITTED:

            if assignment.reviewer:

                template = NotificationTemplateBuilder.build(
                    context,
                    recipient_type="reviewer_submit",
                )

                if template:

                    notifications.append({
                        "company": assignment.company,
                        "sender": context.actor,
                        "recipient": assignment.reviewer,
                        "module": EMISSION,
                        "notification_type": "SUBMITTED",
                        "title": template["title"],
                        "message": template["message"],
                        "reference_id": assignment.id,
                        "action_url": (
                            f"/emission/assignments/"
                            f"{assignment.id}/"
                        ),
                    })

        # =================================================
        # 3. REVIEW REJECTED
        # Assignee gets notification
        # =================================================

        elif context.action == REVIEW_REJECTED:

            if assignment.assignee:

                template = NotificationTemplateBuilder.build(
                    context,
                    recipient_type="assignee",
                )

                if template:

                    notifications.append({
                        "company": assignment.company,
                        "sender": context.actor,
                        "recipient": assignment.assignee,
                        "module": EMISSION,
                        "notification_type": "REJECTED",
                        "title": template["title"],
                        "message": template["message"],
                        "reference_id": assignment.id,
                        "action_url": (
                            f"/emission/assignments/"
                            f"{assignment.id}/"
                        ),
                    })

        # =================================================
        # 4. REVIEW APPROVED
        # Assignee + Assigner get notification
        # =================================================

        elif context.action == REVIEW_APPROVED:

            template = NotificationTemplateBuilder.build(
                context,
                recipient_type="review_approved",
            )

            if template:

                # -----------------------------
                # Assignee
                # -----------------------------

                if assignment.assignee:

                    notifications.append({
                        "company": assignment.company,
                        "sender": context.actor,
                        "recipient": assignment.assignee,
                        "module": EMISSION,
                        "notification_type": "APPROVED",
                        "title": template["title"],
                        "message": template["message"],
                        "reference_id": assignment.id,
                        "action_url": (
                            f"/emission/assignments/"
                            f"{assignment.id}/"
                        ),
                    })

                # -----------------------------
                # Assigner
                # -----------------------------

                if assignment.assigner:

                    notifications.append({
                        "company": assignment.company,
                        "sender": context.actor,
                        "recipient": assignment.assigner,
                        "module": EMISSION,
                        "notification_type": "APPROVED",
                        "title": template["title"],
                        "message": template["message"],
                        "reference_id": assignment.id,
                        "action_url": (
                            f"/emission/assignments/"
                            f"{assignment.id}/"
                        ),
                    })

        # =================================================
        # 5. FINAL APPROVED
        # Assignee + Reviewer get notification
        # =================================================

        elif context.action == FINAL_APPROVED:

            template = NotificationTemplateBuilder.build(
                context,
                recipient_type="final_approved",
            )

            if template:

                # -----------------------------
                # Assignee
                # -----------------------------

                if assignment.assignee:

                    notifications.append({
                        "company": assignment.company,
                        "sender": context.actor,
                        "recipient": assignment.assignee,
                        "module": EMISSION,
                        "notification_type": "APPROVED",
                        "title": template["title"],
                        "message": template["message"],
                        "reference_id": assignment.id,
                        "action_url": (
                            f"/emission/assignments/"
                            f"{assignment.id}/"
                        ),
                    })

                # -----------------------------
                # Reviewer
                # -----------------------------

                if assignment.reviewer:

                    notifications.append({
                        "company": assignment.company,
                        "sender": context.actor,
                        "recipient": assignment.reviewer,
                        "module": EMISSION,
                        "notification_type": "APPROVED",
                        "title": template["title"],
                        "message": template["message"],
                        "reference_id": assignment.id,
                        "action_url": (
                            f"/emission/assignments/"
                            f"{assignment.id}/"
                        ),
                    })

        # =================================================
        # 6. FINAL REJECTED
        # Assignee + Reviewer get notification
        # =================================================

        elif context.action == FINAL_REJECTED:

            template = NotificationTemplateBuilder.build(
                context,
                recipient_type="final_rejected",
            )

            if template:

                # -----------------------------
                # Assignee
                # -----------------------------

                if assignment.assignee:

                    notifications.append({
                        "company": assignment.company,
                        "sender": context.actor,
                        "recipient": assignment.assignee,
                        "module": EMISSION,
                        "notification_type": "REJECTED",
                        "title": template["title"],
                        "message": template["message"],
                        "reference_id": assignment.id,
                        "action_url": (
                            f"/emission/assignments/"
                            f"{assignment.id}/"
                        ),
                    })

                # -----------------------------
                # Reviewer
                # -----------------------------

                if assignment.reviewer:

                    notifications.append({
                        "company": assignment.company,
                        "sender": context.actor,
                        "recipient": assignment.reviewer,
                        "module": EMISSION,
                        "notification_type": "REJECTED",
                        "title": template["title"],
                        "message": template["message"],
                        "reference_id": assignment.id,
                        "action_url": (
                            f"/emission/assignments/"
                            f"{assignment.id}/"
                        ),
                    })

        return notifications

    # =====================================================
    # TIMESHEET
    # =====================================================

    @classmethod
    def build_timesheet(cls, context):

        # IMPORTANT:
        # Timesheet is only created for ASSIGNED event.
        # No reviewer/final-stage timesheets.

        if context.action != ASSIGNED:
            return None

        assignment = context.target

        if not assignment.assignee:
            return None

        return {

            "user": assignment.assignee,

            "assignment": assignment,

            "company": assignment.company,

            "title": (
                f"Timesheet: "
                f"{assignment.scope.name}"
            ),

            "description": (
                f"Data collection for "
                f"{assignment.scope.name} "
                f"({assignment.assignment_code})"
            ),

            "start_date": assignment.created_at,

            "end_date": assignment.due_date,

            "status": "assigned",

            "hours_worked": 0,

            "notification": None,

        }

    # =====================================================
    # EMAIL
    # =====================================================

    @classmethod
    def build_email(cls, context):

        assignment = context.target

        emails = []

        # =====================================================
        # ASSIGNED
        # Assignee + Reviewer
        # =====================================================

        if context.action == ASSIGNED:

            # -------------------------------------------------
            # Assignee
            # -------------------------------------------------

            if assignment.assignee and assignment.assignee.email:

                emails.append({
                    "recipient": assignment.assignee,

                    "subject": (
                        f"New Data Collection Task - "
                        f"{assignment.scope.name}"
                    ),

                    "message": (
                        f"Hello "
                        f"{assignment.assignee.get_full_name() or assignment.assignee.username},\n\n"

                        f"You have been assigned a new data collection task.\n\n"

                        f"Scope: {assignment.scope.name}\n"
                        f"Plant: {assignment.plant.name}\n"
                        f"Reporting Period: "
                        f"{assignment.financial_month.month_name} "
                        f"{assignment.financial_year.financial_year}\n"
                        f"Assigned By: "
                        f"{context.actor.get_full_name() or context.actor.username}\n"
                        f"Due Date: {assignment.due_date or 'Not Specified'}\n\n"

                        f"Please complete the assigned activity "
                        f"before the due date."
                    ),

                    "html_template": "emails/emission/assignment_assigned.html",

                    "context": {
                        "assignment": assignment,
                        "recipient_type": "assignee",
                        "assignment_url": f"{settings.SITE_URL}/emission/assignments/{assignment.id}/",
                    },
                })

            # -------------------------------------------------
            # Reviewer
            # -------------------------------------------------

            if assignment.reviewer and assignment.reviewer.email:

                emails.append({
                    "recipient": assignment.reviewer,

                    "subject": (
                        f"You Have a New Task to Review - "
                        f"{assignment.scope.name}"
                    ),

                    "message": (
                        f"Hello "
                        f"{assignment.reviewer.get_full_name() or assignment.reviewer.username},\n\n"

                        f"You have been appointed as the reviewer "
                        f"for a new data collection assignment.\n\n"

                        f"Scope: {assignment.scope.name}\n"
                        f"Plant: {assignment.plant.name}\n"
                        f"Assigned To: "
                        f"{assignment.assignee.get_full_name() or assignment.assignee.username}\n"
                        f"Reporting Period: "
                        f"{assignment.financial_month.month_name} "
                        f"{assignment.financial_year.financial_year}\n"
                        f"Assigned By: "
                        f"{context.actor.get_full_name() or context.actor.username}\n\n"

                        f"You will receive another notification when "
                        f"the assignee submits the data for your review."
                    ),

                    "html_template": "emails/emission/assignment_assigned.html",

                    "context": {
                        "assignment": assignment,
                        "recipient_type": "reviewer",
                        "assignment_url": f"{settings.SITE_URL}/emission/assignments/{assignment.id}/",
                    },
                })

        # =====================================================
        # SUBMITTED
        # Reviewer
        # =====================================================

        elif context.action == SUBMITTED:

            if assignment.reviewer and assignment.reviewer.email:

                emails.append({
                    "recipient": assignment.reviewer,

                    "subject": (
                        f"Assignment Ready for Review - "
                        f"{assignment.scope.name}"
                    ),

                    "message": (
                        f"Hello "
                        f"{assignment.reviewer.get_full_name() or assignment.reviewer.username},\n\n"

                        f"{assignment.assignee.get_full_name() or assignment.assignee.username} "
                        f"has submitted the {assignment.scope.name} "
                        f"data for review.\n\n"

                        f"Plant: {assignment.plant.name}\n"
                        f"Reporting Period: "
                        f"{assignment.financial_month.month_name} "
                        f"{assignment.financial_year.financial_year}\n\n"

                        f"Please review the submitted data and "
                        f"approve or reject it."
                    ),

                    "html_template": (
                        "emails/emission/assignment_submitted.html"
                    ),

                    "context": {
                        "assignment": assignment,
                        "recipient_type": "reviewer",
                        "assignment_url": (
                            f"{settings.SITE_URL}"
                            f"/emission/assignments/{assignment.id}/"
                        ),
                    },
                })
                
        # =====================================================
        # REVIEW REJECTED
        # Assignee
        # =====================================================

        elif context.action == REVIEW_REJECTED:

            if assignment.assignee and assignment.assignee.email:

                emails.append({
                    "recipient": assignment.assignee,

                    "subject": (
                        f"Changes Required - "
                        f"{assignment.scope.name}"
                    ),

                    "message": (
                        f"Hello "
                        f"{assignment.assignee.get_full_name() or assignment.assignee.username},\n\n"

                        f"The reviewer has requested changes "
                        f"to your {assignment.scope.name} submission.\n\n"

                        f"Assignment: {assignment.assignment_code}\n"
                        f"Plant: {assignment.plant.name}\n"
                        f"Reporting Period: "
                        f"{assignment.financial_month.month_name} "
                        f"{assignment.financial_year.financial_year}\n"
                        f"Reviewed By: "
                        f"{context.actor.get_full_name() or context.actor.username}\n\n"

                        f"Reviewer Comments:\n"
                        f"{assignment.review_comments or 'No comments provided.'}\n\n"

                        f"Please make the required changes and "
                        f"resubmit the data."
                    ),

                    "html_template": (
                        "emails/emission/review_rejected.html"
                    ),

                    "context": {
                        "assignment": assignment,
                        "recipient_type": "assignee",
                        "assignment_url": (
                            f"{settings.SITE_URL}"
                            f"/emission/assignments/{assignment.id}/"
                        ),
                    },
                })

        # =====================================================
        # REVIEW APPROVED
        #
        # Assignee + Assigner
        # =====================================================

        elif context.action == REVIEW_APPROVED:

            # =====================================================
            # Assignee
            # =====================================================

            if assignment.assignee and assignment.assignee.email:

                emails.append({
                    "recipient": assignment.assignee,

                    "subject": (
                        f"Your Submission Has Been Reviewed - "
                        f"{assignment.scope.name}"
                    ),

                    "message": (
                        f"Hello "
                        f"{assignment.assignee.get_full_name() or assignment.assignee.username},\n\n"

                        f"Your {assignment.scope.name} emission data "
                        f"submission has been reviewed and approved by "
                        f"{context.actor.get_full_name() or context.actor.username}.\n\n"

                        f"Assignment: {assignment.assignment_code}\n"
                        f"Plant: {assignment.plant.name}\n"
                        f"Reporting Period: "
                        f"{assignment.financial_month.month_name} "
                        f"{assignment.financial_year.financial_year}\n\n"

                        f"The assignment is now awaiting final approval."
                    ),

                    "html_template": (
                        "emails/emission/review_approved.html"
                    ),

                    "context": {
                        "assignment": assignment,
                        "recipient_type": "assignee",
                        "assignment_url": (
                            f"{settings.SITE_URL}"
                            f"/emission/assignments/{assignment.id}/"
                        ),
                    },
                })


            # =====================================================
            # Assigner
            # =====================================================

            if assignment.assigner and assignment.assigner.email:

                emails.append({
                    "recipient": assignment.assigner,

                    "subject": (
                        f"Submission Ready for Final Approval - "
                        f"{assignment.scope.name}"
                    ),

                    "message": (
                        f"Hello "
                        f"{assignment.assigner.get_full_name() or assignment.assigner.username},\n\n"

                        f"The reviewer has approved the {assignment.scope.name} "
                        f"emission data submission.\n\n"

                        f"Assignment: {assignment.assignment_code}\n"
                        f"Plant: {assignment.plant.name}\n"
                        f"Reporting Period: "
                        f"{assignment.financial_month.month_name} "
                        f"{assignment.financial_year.financial_year}\n"
                        f"Reviewed By: "
                        f"{context.actor.get_full_name() or context.actor.username}\n\n"

                        f"Please review the submission and provide your final approval."
                    ),

                    "html_template": (
                        "emails/emission/review_approved.html"
                    ),

                    "context": {
                        "assignment": assignment,
                        "recipient_type": "assigner",
                        "assignment_url": (
                            f"{settings.SITE_URL}"
                            f"/emission/assignments/{assignment.id}/"
                        ),
                    },
                })

        # =====================================================
        # FINAL REJECTED
        #
        # Assignee + Reviewer
        # =====================================================

        elif context.action == FINAL_REJECTED:

            # -------------------------------------------------
            # Assignee
            # -------------------------------------------------

            if assignment.assignee and assignment.assignee.email:

                emails.append({
                    "recipient": assignment.assignee,

                    "subject": (
                        f"Changes Required Before Final Approval - "
                        f"{assignment.scope.name}"
                    ),

                    "message": (
                        f"Hello "
                        f"{assignment.assignee.get_full_name() or assignment.assignee.username},\n\n"

                        f"Final approval has been rejected for your "
                        f"{assignment.scope.name} submission.\n\n"

                        f"Rejected By: "
                        f"{context.actor.get_full_name() or context.actor.username}\n"
                        f"Plant: {assignment.plant.name}\n"
                        f"Reporting Period: "
                        f"{assignment.financial_month.month_name} "
                        f"{assignment.financial_year.financial_year}\n\n"

                        f"Please review the comments and make the "
                        f"required changes."
                    ),

                    "html_template": "emails/emission/assignment_assigned.html",

                    "context": {
                        "assignment": assignment,
                        "recipient_type": "assignee",
                    },
                })

            # -------------------------------------------------
            # Reviewer
            # -------------------------------------------------

            if assignment.reviewer and assignment.reviewer.email:

                emails.append({
                    "recipient": assignment.reviewer,

                    "subject": (
                        f"Assignment Returned for Changes - "
                        f"{assignment.scope.name}"
                    ),

                    "message": (
                        f"Hello "
                        f"{assignment.reviewer.get_full_name() or assignment.reviewer.username},\n\n"

                        f"The final approval for the "
                        f"{assignment.scope.name} submission has been rejected.\n\n"

                        f"Rejected By: "
                        f"{context.actor.get_full_name() or context.actor.username}\n"
                        f"Submitted By: "
                        f"{assignment.assignee.get_full_name() or assignment.assignee.username}\n\n"

                        f"The assignment has been returned for changes."
                    ),

                    "html_template": "emails/emission/assignment_assigned.html",

                    "context": {
                        "assignment": assignment,
                        "recipient_type": "reviewer",
                    },
                })

        # =====================================================
        # FINAL APPROVED
        #
        # Assignee + Reviewer
        # =====================================================

        elif context.action == FINAL_REJECTED:

            # =====================================================
            # Assignee
            # =====================================================

            if assignment.assignee and assignment.assignee.email:

                emails.append({
                    "recipient": assignment.assignee,

                    "subject": (
                        f"Final Approval Changes Required - "
                        f"{assignment.scope.name}"
                    ),

                    "message": (
                        f"Hello "
                        f"{assignment.assignee.get_full_name() or assignment.assignee.username},\n\n"

                        f"The final approver has requested changes "
                        f"to your {assignment.scope.name} emission assignment.\n\n"

                        f"Assignment: {assignment.assignment_code}\n"
                        f"Plant: {assignment.plant.name}\n"
                        f"Reporting Period: "
                        f"{assignment.financial_month.month_name} "
                        f"{assignment.financial_year.financial_year}\n"
                        f"Final Approver: "
                        f"{context.actor.get_full_name() or context.actor.username}\n\n"

                        f"Comments:\n"
                        f"{assignment.coordinator_comments or 'No comments provided.'}\n\n"

                        f"Please make the required changes and resubmit the data."
                    ),

                    "html_template": (
                        "emails/emission/final_rejected.html"
                    ),

                    "context": {
                        "assignment": assignment,
                        "recipient_type": "assignee",
                        "assignment_url": (
                            f"{settings.SITE_URL}"
                            f"/emission/assignments/{assignment.id}/"
                        ),
                    },
                })


            # =====================================================
            # Reviewer
            # =====================================================

            if assignment.reviewer and assignment.reviewer.email:

                emails.append({
                    "recipient": assignment.reviewer,

                    "subject": (
                        f"Assignment Returned for Changes - "
                        f"{assignment.scope.name}"
                    ),

                    "message": (
                        f"Hello "
                        f"{assignment.reviewer.get_full_name() or assignment.reviewer.username},\n\n"

                        f"The final approver has returned the "
                        f"{assignment.scope.name} emission assignment "
                        f"for changes.\n\n"

                        f"Assignment: {assignment.assignment_code}\n"
                        f"Plant: {assignment.plant.name}\n"
                        f"Reporting Period: "
                        f"{assignment.financial_month.month_name} "
                        f"{assignment.financial_year.financial_year}\n"
                        f"Final Approver: "
                        f"{context.actor.get_full_name() or context.actor.username}\n\n"

                        f"Comments:\n"
                        f"{assignment.coordinator_comments or 'No comments provided.'}\n\n"

                        f"Please review the comments and coordinate with "
                        f"the assignee for the required changes."
                    ),

                    "html_template": (
                        "emails/emission/final_rejected.html"
                    ),

                    "context": {
                        "assignment": assignment,
                        "recipient_type": "reviewer",
                        "assignment_url": (
                            f"{settings.SITE_URL}"
                            f"/emission/assignments/{assignment.id}/"
                        ),
                    },
                })


        elif context.action == FINAL_APPROVED:

            # =====================================================
            # Assignee
            # =====================================================

            if assignment.assignee and assignment.assignee.email:

                emails.append({
                    "recipient": assignment.assignee,

                    "subject": (
                        f"Emission Assignment Fully Approved - "
                        f"{assignment.scope.name}"
                    ),

                    "message": (
                        f"Hello "
                        f"{assignment.assignee.get_full_name() or assignment.assignee.username},\n\n"

                        f"Your {assignment.scope.name} emission data "
                        f"assignment has been fully approved.\n\n"

                        f"Assignment: {assignment.assignment_code}\n"
                        f"Plant: {assignment.plant.name}\n"
                        f"Reporting Period: "
                        f"{assignment.financial_month.month_name} "
                        f"{assignment.financial_year.financial_year}\n"
                        f"Reviewed By: "
                        f"{assignment.reviewer.get_full_name() or assignment.reviewer.username}\n"
                        f"Final Approved By: "
                        f"{context.actor.get_full_name() or context.actor.username}\n\n"

                        f"No further action is required."
                    ),

                    "html_template": (
                        "emails/emission/final_approved.html"
                    ),

                    "context": {
                        "assignment": assignment,
                        "recipient_type": "assignee",
                        "assignment_url": (
                            f"{settings.SITE_URL}"
                            f"/emission/assignments/{assignment.id}/"
                        ),
                    },
                })


            # =====================================================
            # Reviewer
            # =====================================================

            if assignment.reviewer and assignment.reviewer.email:

                emails.append({
                    "recipient": assignment.reviewer,

                    "subject": (
                        f"Emission Assignment Fully Approved - "
                        f"{assignment.scope.name}"
                    ),

                    "message": (
                        f"Hello "
                        f"{assignment.reviewer.get_full_name() or assignment.reviewer.username},\n\n"

                        f"The {assignment.scope.name} emission data "
                        f"submission you reviewed has received final approval.\n\n"

                        f"Assignment: {assignment.assignment_code}\n"
                        f"Plant: {assignment.plant.name}\n"
                        f"Reporting Period: "
                        f"{assignment.financial_month.month_name} "
                        f"{assignment.financial_year.financial_year}\n"
                        f"Final Approved By: "
                        f"{context.actor.get_full_name() or context.actor.username}\n\n"

                        f"No further action is required."
                    ),

                    "html_template": (
                        "emails/emission/final_approved.html"
                    ),

                    "context": {
                        "assignment": assignment,
                        "recipient_type": "reviewer",
                        "assignment_url": (
                            f"{settings.SITE_URL}"
                            f"/emission/assignments/{assignment.id}/"
                        ),
                    },
                })

                
        return emails
    # =====================================================
    # AUDIT
    # =====================================================

    @classmethod
    def build_audit(cls, context):

        return None