from apps.common_events.adapter_registry import ADAPTER_REGISTRY
from apps.email_master.services import EmailService


class EmailHandler:

    @classmethod
    def handle(cls, context):

        # -------------------------------------------------
        # Get module adapter
        # -------------------------------------------------

        adapter = ADAPTER_REGISTRY.get(context.module)

        if not adapter:
            return

        # -------------------------------------------------
        # Build email payload(s)
        # -------------------------------------------------

        emails = adapter.build_email(context)

        if not emails:
            return

        # -------------------------------------------------
        # Send emails
        # -------------------------------------------------

        for email in emails:

            if not email:
                continue

            EmailService.send_email(
                recipient=email["recipient"],
                subject=email["subject"],
                message=email["message"],
                html_template=email.get("html_template"),
                context=email.get("context"),
            )