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
                f"Scope : {assignment.scope.name}\n"
                f"Plant : {assignment.plant.name}\n"
                f"Reporting Period : "
                f"{assignment.financial_month.month_name} "
                f"{assignment.financial_year.financial_year}\n"
                f"Assigned By : "
                f"{sender.get_full_name() or sender.username}\n"
                f"Due Date : {due_date}\n\n"
                f"Please complete the assigned activity before the due date."
            )

        }

    @staticmethod
    def assigned_to_reviewer(assignment, sender):

        return {

            "title": "👀 Review Assignment Scheduled",

            "message": (
                f"Scope : {assignment.scope.name}\n"
                f"Plant : {assignment.plant.name}\n"
                f"Assigned To : "
                f"{assignment.assignee.get_full_name() or assignment.assignee.username}\n"
                f"Reporting Period : "
                f"{assignment.financial_month.month_name} "
                f"{assignment.financial_year.financial_year}\n\n"
                f"You will receive this assignment after data submission."
            )

        }

    @staticmethod
    def submitted_to_reviewer(assignment, sender):

        return {

            "title": "📨 Assignment Ready for Review",

            "message": (
                f"{assignment.assignee.get_full_name() or assignment.assignee.username} "
                f"has submitted the {assignment.scope.name} data.\n"
                f"Please review and approve or reject the submission."
            )

        }

    # =====================================================
    # Reviewer Approved
    # =====================================================

    @staticmethod
    def review_approved(assignment, sender):

        return {

            "title": "✅ Review Completed",

            "message": (
                f"The reviewer "
                f"{sender.get_full_name() or sender.username} "
                f"has approved the submitted data.\n"
                f"The assignment is now awaiting final approval from the ESG Coordinator."
            )

        }

    # =====================================================
    # Reviewer Rejected
    # =====================================================

    @staticmethod
    def review_rejected(assignment, sender):

        return {

            "title": "❌ Reviewer Requested Changes",

            "message": (
                f"The reviewer "
                f"{sender.get_full_name() or sender.username} "
                f"has requested changes to "
                f"{assignment.scope.name}.\n"
                f"Please review the comments and resubmit the data."
            )

        }

    # =====================================================
    # Final Approved
    # =====================================================

    @staticmethod
    def final_approved(assignment, sender):

        return {

            "title": "🎉 Assignment Approved",

            "message": (
                f"The ESG Coordinator "
                f"{sender.get_full_name() or sender.username} "
                f"has given final approval for "
                f"{assignment.scope.name}."
            )

        }

    # =====================================================
    # Final Rejected
    # =====================================================

    @staticmethod
    def final_rejected(assignment, sender):

        return {

            "title": "⚠️ Coordinator Requested Changes",

            "message": (
                f"The ESG Coordinator "
                f"{sender.get_full_name() or sender.username} "
                f"has requested changes before final approval.\n"
                f"Please review the comments and update the submission."
            )

        }