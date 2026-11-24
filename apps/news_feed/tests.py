from datetime import timedelta
from urllib.parse import parse_qs, urlsplit

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
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


class NewsEventEmailLinkTests(TestCase):
    def test_email_detail_redirects_to_login_then_returns_to_detail(self):
        user = get_user_model().objects.create_user(
            username="email-link-user",
            password="test-password",
        )
        content = NewsEvent.objects.create(
            title="Email link event",
            description="Details from the email",
            status=NewsEvent.Status.PUBLISHED,
            all_plants=True,
        )
        detail_url = reverse(
            "news_events:news_event_public_detail",
            kwargs={"pk": content.pk},
        )

        response = self.client.get(detail_url)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(urlsplit(response.url).path, reverse("accounts:login"))
        self.assertEqual(
            parse_qs(urlsplit(response.url).query)["next"],
            [detail_url],
        )

        response = self.client.post(
            reverse("accounts:login"),
            {
                "username": user.username,
                "password": "test-password",
                "next": detail_url,
            },
        )
        self.assertRedirects(
            response,
            detail_url,
            fetch_redirect_response=False,
        )
        self.assertEqual(self.client.get(detail_url).status_code, 200)

    def test_login_rejects_external_next_url(self):
        user = get_user_model().objects.create_user(
            username="email-link-user",
            password="test-password",
        )

        response = self.client.post(
            reverse("accounts:login"),
            {
                "username": user.username,
                "password": "test-password",
                "next": "https://example.com/",
            },
        )

        self.assertRedirects(
            response,
            reverse("accounts:dashboard"),
            fetch_redirect_response=False,
        )
