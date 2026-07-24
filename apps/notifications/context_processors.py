from .models import Notification


def notification_context(request):

    if not request.user.is_authenticated:
        return {}

    queryset = (
        Notification.objects
        .filter(recipient=request.user)
        .select_related("sender")
        .order_by("-created_at")
    )

    unread_count = queryset.filter(
        is_read=False
    ).count()

    notifications = queryset[:5]

    return {
        "navbar_notifications": notifications,
        "navbar_notification_count": unread_count,
    }           