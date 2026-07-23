from .models import Notification


class NotificationService:

    @staticmethod
    def create_notification(
        *,
        company,
        sender,
        recipient,
        module,
        notification_type,
        title,
        message,
        reference_id=None,
        action_url=None,
    ):
        
        print("=" * 50)
        print("Notification Service Called")
        print("Recipient:", recipient)
        print("Title:", title)
        print("=" * 50)

        return Notification.objects.create(
            company=company,
            sender=sender,
            recipient=recipient,
            module=module,
            notification_type=notification_type,
            title=title,
            message=message,
            reference_id=reference_id,
            action_url=action_url,
        )