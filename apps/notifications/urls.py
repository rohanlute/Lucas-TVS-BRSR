from django.urls import path

from .views import NotificationListView
from .api_views import NotificationListAPIView

app_name = "notifications"

urlpatterns = [
    path("notification_list/",NotificationListView.as_view(),name="notification_list"),
    path("api/list/",NotificationListAPIView.as_view(),name="notification-list"),
]