"""Recipient resolution and email delivery for scheduled News/Events."""

import logging

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db.models import Q, QuerySet
from django.urls import reverse
from django.utils import timezone

from apps.email_master.services import EmailService

from .models import NewsEvent, NewsEventActivity


logger = logging.getLogger(__name__)


def get_news_event_recipients(content):
    """Return active users narrowed only by the item's plant/department audience."""
    user_model = get_user_model()
    user_fields = {field.name for field in user_model._meta.get_fields()}
    recipients = user_model.objects.filter(is_active=True)

    plant_ids = list(
        content.plants.filter(is_active=True).values_list("pk", flat=True)
    )
    if not content.all_plants:
        if not plant_ids:
            return recipients.none()
        active_plant_ids = list(
            content.plants.model.objects.filter(is_active=True).values_list(
                "pk", flat=True
            )
        )
        targets_all_active_plants = bool(active_plant_ids) and set(
            plant_ids
        ).issuperset(set(active_plant_ids))

        if not targets_all_active_plants:
            if "assigned_plants" in user_fields:
                recipients = recipients.filter(
                    Q(assigned_plants__in=plant_ids)
                    | Q(assigned_plants__isnull=True)
                )
            elif "plant" in user_fields:
                recipients = recipients.filter(plant_id__in=plant_ids)
            else:
                return recipients.none()

    department_ids = list(
        content.departments.filter(is_active=True).values_list("pk", flat=True)
    )
    if department_ids:
        if "department" in user_fields:
            recipients = recipients.filter(department_id__in=department_ids)
        elif "departments" in user_fields:
            recipients = recipients.filter(departments__in=department_ids)
        else:
            return []

    return recipients.order_by().distinct()


def get_news_event_recipient_emails(content):
    """Return unique active recipient email addresses for an item."""
    return list(
        get_news_event_recipients(content)
        .exclude(email__isnull=True)
        .exclude(email="")
        .values_list("email", flat=True)
        .distinct()
    )


def _absolute_detail_url(content):
    relative_url = reverse(
        "news_events:news_event_public_detail",
        kwargs={"pk": content.pk},
    )
    site_url = getattr(settings, "SITE_URL", "").rstrip("/")
    return f"{site_url}{relative_url}" if site_url else relative_url


def _email_payload(delivery):
    content = delivery.content
    is_reminder = (
        delivery.delivery_type == delivery.DeliveryType.REMINDER
    )
    item_type = "event" if content.is_event else "news"

    if is_reminder:
        days_before = delivery.reminder_rule.days_before
        subject = f"Reminder: {content.title} is in {days_before} day(s)"
        template = "emails/news_feed/event_reminder.html"
        purpose = "A reminder for an upcoming event."
    elif content.is_event:
        subject = f"Upcoming event: {content.title}"
        template = "emails/news_feed/event_announcement.html"
        purpose = "An upcoming event for your plant and department audience."
        days_before = None
    else:
        subject = f"News update: {content.title}"
        template = "emails/news_feed/news_announcement.html"
        purpose = "A news update for your plant and department audience."
        days_before = None

    event_start = (
        timezone.localtime(content.start_datetime)
        if content.start_datetime else None
    )
    event_end = (
        timezone.localtime(content.end_datetime)
        if content.end_datetime else None
    )
    context = {
        "content": content,
        "item_type": item_type,
        "purpose": purpose,
        "detail_url": _absolute_detail_url(content),
        "event_start": event_start,
        "event_end": event_end,
        "meeting_link": content.meeting_link,
        "days_before": days_before,
    }
    message = f"{content.title}\n\n{content.description}\n\nView details: {context['detail_url']}"
    if event_start:
        message += f"\nEvent starts: {event_start.strftime('%d %B %Y, %I:%M %p')}"
    if event_end:
        message += f"\nEvent ends: {event_end.strftime('%d %B %Y, %I:%M %p')}"
    if content.meeting_link:
        message += f"\nMeeting link: {content.meeting_link}"
    return subject, message, template, context


def _mark_delivery(delivery, *, status, error_message=""):
    delivery.status = status
    delivery.sent_at = timezone.now() if status == delivery.Status.SENT else None
    delivery.error_message = error_message[:4000]
    delivery.save(
        update_fields=["status", "sent_at", "error_message", "updated_at"]
    )


def send_delivery_email(delivery):
    """Send one due announcement/reminder delivery to its resolved audience."""
    content = delivery.content
    if content.status not in (NewsEvent.Status.PUBLISHED, NewsEvent.Status.SCHEDULED):
        _mark_delivery(
            delivery,
            status=delivery.Status.CANCELLED,
            error_message="The News/Event is no longer active.",
        )
        return 0

    if not content.send_email:
        _mark_delivery(
            delivery,
            status=delivery.Status.SKIPPED,
            error_message="Email notifications are disabled for this item.",
        )
        return 0

    if delivery.delivery_type == delivery.DeliveryType.REMINDER:
        rule = delivery.reminder_rule
        if not content.is_event or not rule or not rule.is_active:
            _mark_delivery(
                delivery,
                status=delivery.Status.CANCELLED,
                error_message="The event reminder rule is no longer active.",
            )
            return 0
    elif delivery.delivery_type != delivery.DeliveryType.ANNOUNCEMENT:
        _mark_delivery(
            delivery,
            status=delivery.Status.SKIPPED,
            error_message="This delivery type does not send email.",
        )
        return 0

    recipient_emails = get_news_event_recipient_emails(content)
    if not recipient_emails:
        _mark_delivery(
            delivery,
            status=delivery.Status.SKIPPED,
            error_message="No active users with email addresses match this audience.",
        )
        logger.warning("No email recipients for News/Event delivery %s", delivery.pk)
        return 0

    subject, message, template, context = _email_payload(delivery)
    sent_count = 0
    failed_count = 0
    for recipient_email in recipient_emails:
        if EmailService.send_email(
            recipient=recipient_email,
            subject=subject,
            message=message,
            html_template=template,
            context=context,
        ):
            sent_count += 1
        else:
            failed_count += 1

    if failed_count:
        _mark_delivery(
            delivery,
            status=delivery.Status.FAILED,
            error_message=(
                f"Email sent to {sent_count} recipient(s); "
                f"failed for {failed_count} recipient(s)."
            ),
        )
        content.activity_logs.create(
            action=NewsEventActivity.Action.DELIVERY_FAILED,
            note=f"{delivery.get_delivery_type_display()} email delivery partially failed.",
            metadata={
                "delivery_id": delivery.pk,
                "sent_count": sent_count,
                "failed_count": failed_count,
            },
        )
        return sent_count

    _mark_delivery(delivery, status=delivery.Status.SENT)
    if delivery.delivery_type == delivery.DeliveryType.REMINDER:
        content.activity_logs.create(
            action=NewsEventActivity.Action.REMINDER_SENT,
            note=f"Event reminder sent to {sent_count} user(s).",
            metadata={"delivery_id": delivery.pk, "sent_count": sent_count},
        )
    logger.info(
        "Sent %s email delivery %s to %s recipient(s)",
        delivery.get_delivery_type_display(),
        delivery.pk,
        sent_count,
    )
    return sent_count
