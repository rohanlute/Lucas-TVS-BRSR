import logging
from celery import shared_task
from django.db import close_old_connections, transaction
from django.db.models import F
from django.utils import timezone
from .email_delivery import send_delivery_email
from .models import NewsEvent, NewsEventActivity, NewsEventDelivery
from .notification_delivery import send_delivery_notification


logger = logging.getLogger(__name__)


def _claim_and_send_delivery(delivery_id):
    """Claim one pending email or in-app delivery exactly once."""
    now = timezone.now()
    claimed = NewsEventDelivery.objects.filter(
        pk=delivery_id,
        channel__in=[
            NewsEventDelivery.Channel.EMAIL,
            NewsEventDelivery.Channel.IN_APP,
        ],
        status=NewsEventDelivery.Status.PENDING,
    ).update(
        status=NewsEventDelivery.Status.PROCESSING,
        attempt_count=F("attempt_count") + 1,
        last_attempt_at=now,
        updated_at=now,
    )
    if not claimed:
        return 0

    try:
        delivery = NewsEventDelivery.objects.select_related(
            "content", "reminder_rule"
        ).get(pk=delivery_id)
        content = delivery.content

        # Scheduled News uses start_datetime as its publication time.
        if (
            delivery.delivery_type == NewsEventDelivery.DeliveryType.ANNOUNCEMENT
            and not content.is_event
            and content.status == NewsEvent.Status.SCHEDULED
        ):
            with transaction.atomic():
                updated = NewsEvent.objects.filter(
                    pk=content.pk,
                    status=NewsEvent.Status.SCHEDULED,
                ).update(
                    status=NewsEvent.Status.PUBLISHED,
                    published_at=delivery.scheduled_for,
                    updated_at=now,
                )
                if updated:
                    content.refresh_from_db()
                    content.activity_logs.create(
                        action=NewsEventActivity.Action.PUBLISHED,
                        note="News automatically published at its scheduled time.",
                        metadata={"delivery_id": delivery.pk},
                    )
                else:
                    content.refresh_from_db()

        if delivery.channel == NewsEventDelivery.Channel.IN_APP:
            return send_delivery_notification(delivery)
        return send_delivery_email(delivery)
    except Exception as exc:
        logger.exception("News/Event delivery %s failed", delivery_id)
        NewsEventDelivery.objects.filter(pk=delivery_id).update(
            status=NewsEventDelivery.Status.FAILED,
            error_message=str(exc)[:4000],
            updated_at=timezone.now(),
        )
        return 0


def run_news_event_delivery_in_background(delivery_id):
    """Process a publish-time email or bell delivery outside the web request."""
    close_old_connections()
    try:
        return _claim_and_send_delivery(delivery_id)
    finally:
        close_old_connections()


@shared_task(ignore_result=True, name="news_feed.send_news_event_email_delivery")
def send_news_event_email_delivery(delivery_id):
    """Send a single announcement/reminder asynchronously."""
    return _claim_and_send_delivery(delivery_id)


@shared_task(ignore_result=True, name="news_feed.dispatch_due_email_deliveries")
def dispatch_due_email_deliveries(batch_size=100):
    """Claim and process due email and in-app announcement/reminder rows."""
    now = timezone.now()

    # Publication is a content lifecycle action and must happen even if the
    # author opted out of email, so process due scheduled News independently.
    due_news = NewsEvent.objects.filter(
        is_event=False,
        status=NewsEvent.Status.SCHEDULED,
        start_datetime__lte=now,
    ).order_by("start_datetime", "pk").values_list("pk", "start_datetime")[:batch_size]
    for content_id, publication_time in list(due_news):
        with transaction.atomic():
            published = NewsEvent.objects.filter(
                pk=content_id,
                status=NewsEvent.Status.SCHEDULED,
            ).update(
                status=NewsEvent.Status.PUBLISHED,
                published_at=publication_time,
                updated_at=now,
            )
            if published:
                NewsEventActivity.objects.create(
                    content_id=content_id,
                    action=NewsEventActivity.Action.PUBLISHED,
                    note="News automatically published at its scheduled time.",
                    metadata={"scheduled_publication": True},
                )

    eligible = NewsEventDelivery.objects.filter(
        channel__in=[
            NewsEventDelivery.Channel.EMAIL,
            NewsEventDelivery.Channel.IN_APP,
        ],
        delivery_type__in=[
            NewsEventDelivery.DeliveryType.ANNOUNCEMENT,
            NewsEventDelivery.DeliveryType.REMINDER,
        ],
        status=NewsEventDelivery.Status.PENDING,
        scheduled_for__lte=now,
    ).order_by("scheduled_for", "pk").values_list("pk", flat=True)[:batch_size]

    processed = sent_to = 0
    for delivery_id in list(eligible):
        was_pending = NewsEventDelivery.objects.filter(
            pk=delivery_id,
            status=NewsEventDelivery.Status.PENDING,
        ).exists()
        sent_to += _claim_and_send_delivery(delivery_id)
        if was_pending:
            processed += 1

    return {"processed": processed, "emails_sent": sent_to}
