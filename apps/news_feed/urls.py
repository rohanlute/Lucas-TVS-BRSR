from django.urls import path

from . import views


app_name = "news_events"

urlpatterns = [
    path("",views.NewsEventListView.as_view(),name="news_event_list",),
    path("feed/",views.NewsEventFeedView.as_view(),name="news_event_feed",),
    path("events/upcoming/",views.UpcomingEventsListView.as_view(),name="upcoming_events",),
    path("view/<int:pk>/",views.NewsEventPublicDetailView.as_view(),name="news_event_public_detail",),

    # News / Event CRUD
    path("add/",views.NewsEventCreateView.as_view(),name="news_event_create",),
    path("<int:pk>/",views.NewsEventDetailView.as_view(),name="news_event_detail",),
    path("<int:pk>/edit/",views.NewsEventUpdateView.as_view(),name="news_event_update",),
    path("<int:pk>/delete/",views.NewsEventDeleteView.as_view(),name="news_event_delete",),

    # Status actions
    path("<int:pk>/publish/",views.PublishNewsEventView.as_view(),name="news_event_publish",),
    path("<int:pk>/archive/",views.ArchiveNewsEventView.as_view(),name="news_event_archive",),
    path("<int:pk>/restore/",views.RestoreNewsEventView.as_view(),name="news_event_restore",),
    path("<int:pk>/cancel/",views.CancelNewsEventView.as_view(),name="news_event_cancel",),

    # Attachments
    path("attachments/<int:attachment_pk>/delete/",views.NewsEventAttachmentDeleteView.as_view(),name="news_event_attachment_delete",),
]
