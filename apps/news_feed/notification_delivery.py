import logging
from django.urls import reverse
from django.utils import timezone
from apps.notifications.models import Notification
from apps.notifications.services import NotificationService
from .email_delivery import get_news_event_recipients
from .models import NewsEvent, NewsEventDelivery


logger = logging.getLogger(__name__)


def _mark_delivery(delivery, status, error_message=""):
    delivery.status = status
    delivery.sent_at = timezone.now() if status == NewsEventDelivery.Status.SENT else None
    delivery.error_message = error_message[:4000]
    delivery.save(update_fields=["status", "sent_at", "error_message", "updated_at"])


def send_delivery_notification(delivery):
    """Create one shared-model Notification per matching active user."""
    content = delivery.content
    if content.status not in (NewsEvent.Status.PUBLISHED, NewsEvent.Status.SCHEDULED):
        _mark_delivery(
            delivery,
            NewsEventDelivery.Status.CANCELLED,
            "The News/Event is no longer active.",
        )
        return 0

    if not content.send_in_app:
        _mark_delivery(
            delivery,
            NewsEventDelivery.Status.SKIPPED,
            "In-app notifications are disabled for this item.",
        )
        return 0

    is_reminder = delivery.delivery_type == NewsEventDelivery.DeliveryType.REMINDER
    if is_reminder:
        rule = delivery.reminder_rule
        if not content.is_event or not rule or not rule.is_active:
            _mark_delivery(
                delivery,
                NewsEventDelivery.Status.CANCELLED,
                "The event reminder rule is no longer active.",
            )
            return 0
    elif delivery.delivery_type != NewsEventDelivery.DeliveryType.ANNOUNCEMENT:
        _mark_delivery(
            delivery,
            NewsEventDelivery.Status.SKIPPED,
            "This delivery type does not create a notification.",
        )
        return 0

    recipients = get_news_event_recipients(content)

    event_start = (
        timezone.localtime(content.start_datetime)
        if content.start_datetime else None
    )
    if is_reminder:
        title = f"Event reminder: {content.title}"
        days_before = delivery.reminder_rule.days_before
        message = f"{content.title} is in {days_before} day(s). {content.description}"
        notification_type = Notification.NotificationTypeChoices.REMINDER
    elif content.is_event:
        title = f"Upcoming event: {content.title}"
        message = content.description
        notification_type = Notification.NotificationTypeChoices.CREATED
    else:
        title = f"News update: {content.title}"
        message = content.description
        notification_type = Notification.NotificationTypeChoices.CREATED

    if event_start and content.is_event:
        message += f" Event starts {event_start.strftime('%d %b %Y, %I:%M %p')}."
    action_url = reverse(
        "news_events:news_event_public_detail",
        kwargs={"pk": content.pk},
    )

    created_count = 0
    failed_count = 0
    for recipient in recipients:
        company = getattr(recipient, "company", None)
        if company is None and content.created_by:
            company = getattr(content.created_by, "company", None)
        if company is None:
            company = getattr(delivery.content.published_by, "company", None)
        if company is None:
            from apps.companies.models import Company

            company = Company.objects.order_by("pk").first()
        if company is None:
            logger.warning(
                "Skipping News/Event notification for recipient %s: no company is available.",
                recipient.pk,
            )
            failed_count += 1
            continue

        try:
            NotificationService.create(
                company=company,
                sender=content.created_by or recipient,
                recipient=recipient,
                module=Notification.ModuleChoices.NEWS_FEED,
                notification_type=notification_type,
                title=title[:255],
                message=message,
                reference_id=content.pk,
                action_url=action_url,
            )
            created_count += 1
        except Exception:
            failed_count += 1
            logger.exception(
                "Failed to create News/Event notification for recipient %s (delivery %s).",
                recipient.pk,
                delivery.pk,
            )

    result_message = (
        f"Notifications created: {created_count}; failed: {failed_count}."
    )
    if created_count > 0 and failed_count == 0:
        _mark_delivery(
            delivery,
            NewsEventDelivery.Status.SENT,
            result_message,
        )
    elif created_count == 0 and failed_count == 0:
        _mark_delivery(
            delivery,
            NewsEventDelivery.Status.SKIPPED,
            f"{result_message} No active recipients matched the selected audience.",
        )
    else:
        _mark_delivery(
            delivery,
            NewsEventDelivery.Status.FAILED,
            result_message,
        )
    return created_count
