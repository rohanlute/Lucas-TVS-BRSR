from django.conf import settings

from apps.common_events.constants import (
    CREATED,
    KPI_AT_RISK,
    KPI_CRITICAL,
    KPI_NEAR_TARGET,
    KPI_TARGET_ACHIEVED,
)


class GoalsAdapter:

    @classmethod
    def build_email(cls, context):

        goal = context.target
        recipient = context.actor

        # -------------------------------------------------
        # Validate recipient
        # -------------------------------------------------

        if not recipient or not getattr(recipient, "email", None):
            return []

        # -------------------------------------------------
        # Goal Created
        # -------------------------------------------------

        if context.action == CREATED:

            site_url = getattr(settings, "SITE_URL", "").rstrip("/")

            goal_url = (
                f"{site_url}/goals/detail/"
                f"{goal.material_topic.name}/"
                f"?goal={goal.name}"
            )

            full_name = (
                recipient.get_full_name()
                or getattr(recipient, "username", "")
                or "there"
            )

            subject = f"Goal Created: {goal.name}"

            message = f"""Hello {full_name},

A new goal has been created in the Goals module.

Goal: {goal.name}
Material Topic: {goal.material_topic.name}
Created By: {recipient.get_full_name() or recipient.username}

You can review the goal using the link below:

{goal_url}

Regards,
Lucas-TVS BRSR Team
"""

            return [{
                "recipient": recipient,
                "subject": subject,
                "message": message,
                "html_template": "emails/goals/goal_created.html",
                "context": {
                    "goal": goal,
                    "recipient": recipient,
                    "full_name": full_name,
                    "goal_url": goal_url,
                },
            }]

        # -------------------------------------------------
        # KPI Status Emails
        # -------------------------------------------------

        kpi = None

        if context.metadata:
            kpi = context.metadata.get("kpi")

        if not kpi:
            return []

        status = context.metadata.get("status")

        current_value = context.metadata.get("current_value")
        baseline_value = context.metadata.get("baseline_value")
        target_value = context.metadata.get("target_value")

        # -------------------------------------------------
        # Map Event Action -> Email Status
        # -------------------------------------------------

        status_config = {
            KPI_AT_RISK: {
                "status": "AT_RISK",
                "subject": f"Goal At Risk: {kpi.name}",
                "title": "Goal At Risk",
            },

            KPI_CRITICAL: {
                "status": "CRITICAL",
                "subject": f"Goal Critical: {kpi.name}",
                "title": "Goal Critical",
            },

            KPI_NEAR_TARGET: {
                "status": "NEAR_TARGET",
                "subject": f"Goal Nearing Target: {kpi.name}",
                "title": "Goal Nearing Target",
            },

            KPI_TARGET_ACHIEVED: {
                "status": "TARGET_ACHIEVED",
                "subject": f"Goal Target Achieved: {kpi.name}",
                "title": "Goal Target Achieved",
            },
        }

        config = status_config.get(context.action)

        if not config:
            return []

        status = config["status"]

        site_url = getattr(
            settings,
            "SITE_URL",
            "",
        ).rstrip("/")

        goal_url = (
            f"{site_url}/goals/detail/"
            f"{goal.material_topic.name}/"
            f"?goal={goal.name}"
        )

        full_name = (
            recipient.get_full_name()
            or getattr(recipient, "username", "")
            or "there"
        )

        # -------------------------------------------------
        # Build KPI Email
        # -------------------------------------------------

        message = f"""Hello {full_name},

This is a notification regarding the following Goal KPI.

Goal: {goal.name}
Material Topic: {goal.material_topic.name}
KPI: {kpi.name}

Status: {status}

Current Value: {float(current_value or 0):.2f}
Baseline Value: {float(baseline_value or 0):.2f}
Target Value: {float(target_value or 0):.2f}

Please review the Goal and KPI details using the link below:

{goal_url}

Regards,
Lucas-TVS BRSR Team
"""

        return [{
            "recipient": recipient,
            "subject": config["subject"],
            "message": message,
            "html_template": "emails/goals/goal_kpi_status.html",
            "context": {
                "goal": goal,
                "kpi": kpi,
                "recipient": recipient,
                "full_name": full_name,
                "status": status,
                "status_title": config["title"],
                "current_value": current_value,
                "baseline_value": baseline_value,
                "target_value": target_value,
                "goal_url": goal_url,
            },
        }]

    @classmethod
    def build(cls, context):

        return {
            "notification": None,
            "timesheet": None,
            "email": cls.build_email(context),
            "audit": None,
        }