from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from .forms import NewsEventForm
from .models import NewsEvent, NewsEventDelivery
from .views import refresh_delivery_schedules, upcoming_event_queryset


class NewsEventFormTests(TestCase):
    def test_auto_remove_is_not_a_form_option(self):
        self.assertNotIn("auto_remove_after_date", NewsEventForm().fields)


class UpcomingEventTests(TestCase):
    def create_event(self, *, starts_at, ends_at=None, auto_remove=True):
        return NewsEvent.objects.create(
            is_event=True,
            title="Team event",
            description="Event details",
            start_datetime=starts_at,
            end_datetime=ends_at,
            status=NewsEvent.Status.PUBLISHED,
            auto_remove_after_date=auto_remove,
            send_email=False,
            send_in_app=False,
            show_in_news_line=False,
        )

    def test_events_remain_upcoming_until_their_end_time(self):
        now = timezone.now()
        ongoing = self.create_event(
            starts_at=now - timedelta(hours=1),
            ends_at=now + timedelta(hours=1),
        )
        expired = self.create_event(
            starts_at=now - timedelta(hours=2),
            ends_at=now - timedelta(hours=1),
        )
        upcoming = self.create_event(
            starts_at=now + timedelta(hours=1),
            ends_at=now + timedelta(hours=2),
        )

        visible_ids = set(
            upcoming_event_queryset(NewsEvent.objects.all(), now=now).values_list(
                "id", flat=True
            )
        )

        self.assertEqual(visible_ids, {ongoing.id, upcoming.id})
        self.assertNotIn(expired.id, visible_ids)

    def test_expiry_delivery_is_scheduled_even_if_legacy_flag_is_false(self):
        now = timezone.now()
        end_time = now + timedelta(hours=2)
        event = self.create_event(
            starts_at=now + timedelta(hours=1),
            ends_at=end_time,
            auto_remove=False,
        )

        refresh_delivery_schedules(event)

        expiry = event.delivery_schedules.get(
            delivery_type=NewsEventDelivery.DeliveryType.EXPIRY
        )
        self.assertEqual(expiry.scheduled_for, end_time)
