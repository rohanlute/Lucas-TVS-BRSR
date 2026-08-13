from apps.common_events.adapter_registry import ADAPTER_REGISTRY
from apps.notifications.services import NotificationService


class NotificationHandler:

    @classmethod
    def handle(cls, context):

        adapter = ADAPTER_REGISTRY.get(context.module)

        if not adapter:
            return

        notifications = adapter.build_notification(context)

        if not notifications:
            return

        for notification in notifications:

            NotificationService.create(**notification)