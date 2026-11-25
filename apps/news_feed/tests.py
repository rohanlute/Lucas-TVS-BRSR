from datetime import datetime, timedelta
from urllib.parse import parse_qs, urlsplit

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import Department
from apps.organizations.models import Plant

from .forms import NewsEventForm
from .models import NewsEvent, NewsEventDelivery
from .email_delivery import get_news_event_recipients
from .views import refresh_delivery_schedules, upcoming_event_queryset


class NewsEventFormTests(TestCase):
    def test_auto_remove_is_not_a_form_option(self):
        self.assertNotIn("auto_remove_after_date", NewsEventForm().fields)

    def test_start_datetime_cannot_be_before_today(self):
        yesterday = timezone.localdate() - timedelta(days=1)
        form = NewsEventForm(data={
            "is_event": "False",
            "title": "News item",
            "description": "Details",
            "start_datetime": yesterday.strftime("%Y-%m-%dT12:00"),
            "all_plants": "on",
            "status": NewsEvent.Status.DRAFT,
        })

        self.assertFalse(form.is_valid())
        self.assertIn("Date cannot be earlier than today.", form.errors["start_datetime"])

    def test_expiry_datetime_cannot_be_before_publish_date(self):
        today = timezone.localdate()
        start = timezone.make_aware(
            datetime.combine(today + timedelta(days=2), datetime.min.time())
        )
        expiry = timezone.make_aware(
            datetime.combine(today + timedelta(days=1), datetime.min.time())
        )
        form = NewsEventForm(data={
            "is_event": "False",
            "title": "News item",
            "description": "Details",
            "start_datetime": timezone.localtime(start).strftime("%Y-%m-%dT%H:%M"),
            "end_datetime": timezone.localtime(expiry).strftime("%Y-%m-%dT%H:%M"),
            "all_plants": "on",
            "status": NewsEvent.Status.DRAFT,
        })

        self.assertFalse(form.is_valid())
        self.assertIn(
            "Expiry date cannot be before the publish date.",
            form.errors["end_datetime"],
        )


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


class NewsEventRecipientTests(TestCase):
    def test_unassigned_user_receives_when_item_targets_all_active_plants(self):
        department = Department.objects.create(
            name="Environment, Health & Safety",
            code="EHS",
        )
        user = get_user_model().objects.create_user(
            username="divya",
            password="test-password",
            department=department,
            is_active=True,
        )
        plants = [
            Plant.objects.create(
                name=f"Plant {index}",
                code=f"P-{index}",
                address="Test address",
                pincode="000000",
            )
            for index in range(1, 3)
        ]
        content = NewsEvent.objects.create(
            title="All plant announcement",
            description="Details",
            status=NewsEvent.Status.PUBLISHED,
            all_plants=False,
        )
        content.plants.set(plants)
        content.departments.set([department])

        self.assertIn(user, get_news_event_recipients(content))


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
