from django.conf import settings


class GoalsAdapter:

    @classmethod
    def build_email(cls, context):

        goal = context.target
        recipient = context.actor

        # Only handle Goal Created event
        if context.action != "CREATED":
            return []

        # No recipient or email address
        if not recipient or not getattr(recipient, "email", None):
            return []

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

    @classmethod
    def build(cls, context):

        return {
            "notification": None,
            "timesheet": None,
            "email": cls.build_email(context),
            "audit": None,
        }