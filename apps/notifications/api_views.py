from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from .models import Notification


class NotificationListAPIView(APIView):

    def get(self, request):

        notifications = (
            Notification.objects
            .filter(recipient=request.user)
            .select_related(
                "sender",
                "recipient",
                "company",
            )
            .order_by("-created_at")
        )

        data = []

        for notification in notifications:

            data.append({
                "id": notification.id,
                "notification_code": notification.notification_code,
                "title": notification.title,
                "message": notification.message,
                "module": notification.module,
                "notification_type": notification.notification_type,
                "sender": notification.sender.full_name or notification.sender.username,
                "is_read": notification.is_read,
                "action_url": notification.action_url,
                "created_at": notification.created_at.strftime("%d-%m-%Y %I:%M %p"),
            })

        return Response(
            {
                "success": True,
                "count": len(data),
                "notifications": data,
            },
            status=status.HTTP_200_OK,
        )