class AssignmentNotificationTemplates:

    @staticmethod
    def assigned_to_assignee(assignment, sender):

        from datetime import date, datetime

        if not assignment.due_date:
            due_date = "Not Specified"

        elif isinstance(assignment.due_date, (date, datetime)):
            due_date = assignment.due_date.strftime("%d-%b-%Y")

        else:
            due_date = str(assignment.due_date)

        return {
            "title": "📋 New Data Collection Assignment",
            "message": (
                f"Scope: {assignment.scope.name}\n"
                f"Plant: {assignment.plant.name}\n"
                f"Reporting Period: "
                f"{assignment.financial_month.month_name} "
                f"{assignment.financial_year.financial_year}\n"
                f"Assigned By: "
                f"{sender.get_full_name() or sender.username}\n"
                f"Due Date: {due_date}\n\n"
                f"Please complete the assigned activity before the due date."
            ),
        }

    @staticmethod
    def assigned_to_reviewer(assignment, sender):

        return {
            "title": "👀 You Have a New Task to Review",

            "message": (
                f"You have been appointed as the reviewer for "
                f"{assignment.scope.name} data.\n\n"
                f"Plant: {assignment.plant.name}\n"
                f"Assigned To: "
                f"{assignment.assignee.get_full_name() or assignment.assignee.username}\n"
                f"Reporting Period: "
                f"{assignment.financial_month.month_name} "
                f"{assignment.financial_year.financial_year}\n"
                f"Assigned By: "
                f"{sender.get_full_name() or sender.username}\n\n"
                f"You will receive another notification when the "
                f"assignee submits the data for your review."
            ),
        }

    @staticmethod
    def submitted_to_reviewer(assignment, sender):

        return {
            "title": "📨 Assignment Ready for Review",
            "message": (
                f"{assignment.assignee.get_full_name() or assignment.assignee.username} "
                f"has submitted {assignment.scope.name} data.\n\n"
                f"Please review and approve or reject the submission."
            ),
        }

    @staticmethod
    def review_rejected(assignment, sender):

        return {
            "title": "❌ Changes Requested",
            "message": (
                f"{sender.get_full_name() or sender.username} "
                f"has requested changes to "
                f"{assignment.scope.name}.\n\n"
                f"Please review the comments and resubmit the data."
            ),
        }

    @staticmethod
    def review_approved(assignment, sender):

        return {
            "title": "✅ Approved by Reviewer, Waiting for Final Approval",
            "message": (
                f"{sender.get_full_name() or sender.username} "
                f"has approved the {assignment.scope.name} data.\n\n"
                f"The assignment is now awaiting final approval."
            ),
        }

    @staticmethod
    def final_approved(assignment, sender):

        return {
            "title": "🎉 Assignment Approved",
            "message": (
                f"{sender.get_full_name() or sender.username} "
                f"has given final approval for "
                f"{assignment.scope.name}.\n\n"
                f"The assignment is now completed."
            ),
        }

    @staticmethod
    def final_rejected(assignment, sender):

        return {
            "title": "⚠️ Final Approval Changes Requested",
            "message": (
                f"{sender.get_full_name() or sender.username} "
                f"has requested changes to "
                f"{assignment.scope.name} "
                f"before final approval."
            ),
        }