from pathlib import Path
from datetime import time

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator, MinValueValidator
from django.db import models
from django.db.models import F, Q
from django.utils import timezone


PLANT_MODEL = getattr(
    settings, "NEWS_EVENTS_PLANT_MODEL", "organizations.Plant"
)
DEPARTMENT_MODEL = getattr(
    settings, "NEWS_EVENTS_DEPARTMENT_MODEL", "accounts.Department"
)


REMINDER_DAY_CHOICES = (
    (1, "1 day before"),
    (2, "2 days before"),
    (3, "3 days before"),
    (5, "5 days before"),
    (7, "7 days before"),
    (10, "10 days before"),
    (14, "14 days before"),
)


class NewsEvent(models.Model):

    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        SCHEDULED = "SCHEDULED", "Scheduled"
        PUBLISHED = "PUBLISHED", "Published"
        ARCHIVED = "ARCHIVED", "Archived"
        CANCELLED = "CANCELLED", "Cancelled"

    # This boolean is intentionally retained as requested.
    # False = News; True = Event.
    is_event = models.BooleanField(
        default=False,
        db_index=True,
        help_text="False for News and True for Event.",
    )

    title = models.CharField(max_length=255)
    description = models.TextField()

    # For News, start_datetime is the scheduled publication date/time.
    # For Events, it is the event start date/time.
    start_datetime = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
        help_text=(
            "Scheduled publish time for News; event start time for Events."
        ),
    )
    # Event end time, or optional content expiry time for News.
    end_datetime = models.DateTimeField(null=True, blank=True)

    meeting_link = models.URLField(
        max_length=2000,
        blank=True,
        help_text="Optional meeting URL for online or hybrid events.",
    )

    all_plants = models.BooleanField(
        default=False,
        help_text="When enabled, this item is visible to all applicable plants.",
    )
    plants = models.ManyToManyField(
        PLANT_MODEL,
        blank=True,
        related_name="news_event_items",
    )
    departments = models.ManyToManyField(
        DEPARTMENT_MODEL,
        blank=True,
        related_name="news_event_items",
    )

    # Delivery channel switches shown on the Add / Schedule form.
    send_email = models.BooleanField(default=True)
    send_in_app = models.BooleanField(default=True)
    show_in_news_line = models.BooleanField(default=True)

    # The event can be removed from the Upcoming Events area after its date.
    auto_remove_after_date = models.BooleanField(
        default=True,
        help_text="Automatically stop showing this event after its end date/time.",
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
        db_index=True,
    )
    published_at = models.DateTimeField(null=True, blank=True, db_index=True)
    archived_at = models.DateTimeField(null=True, blank=True)
    archived_from_status = models.CharField(
        max_length=20,
        choices=(
            (Status.DRAFT, "Draft"),
            (Status.SCHEDULED, "Scheduled"),
            (Status.PUBLISHED, "Published"),
            (Status.CANCELLED, "Cancelled"),
        ),
        null=True,
        blank=True,
        editable=False,
        help_text="Status to return to when this item is restored.",
    )

    # Audit fields.
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_news_event_items",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="updated_news_event_items",
    )
    published_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="published_news_event_items",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-start_datetime", "-created_at")
        verbose_name = "News / Event"
        verbose_name_plural = "News & Events"
        indexes = [
            models.Index(fields=("is_event", "status", "start_datetime")),
            models.Index(fields=("status", "published_at")),
        ]
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(end_datetime__isnull=True)
                    | Q(start_datetime__isnull=True)
                    | Q(end_datetime__gt=F("start_datetime"))
                ),
                name="news_event_end_after_start",
            ),
        ]

    def __str__(self):
        item_type = "Event" if self.is_event else "News"
        return f"{item_type}: {self.title}"

    def clean(self):
        super().clean()

        errors = {}
        if self.end_datetime and self.start_datetime:
            if self.end_datetime <= self.start_datetime:
                errors["end_datetime"] = (
                    "End date/time must be later than the start date/time."
                )

        if self.is_event and not self.start_datetime:
            errors["start_datetime"] = "An event start date/time is required."

        if self.status == self.Status.SCHEDULED and not self.start_datetime:
            errors["start_datetime"] = (
                "A date/time is required before an item can be scheduled."
            )

        if errors:
            raise ValidationError(errors)

    @property
    def item_type_label(self):
        return "Event" if self.is_event else "News"

    @property
    def event_or_publish_datetime(self):
        """Semantic alias for start_datetime, useful in templates/API output."""
        return self.start_datetime

    @property
    def auto_remove_at(self):
        """Return the event removal time; fall back to its start if no end exists."""
        return self.end_datetime or self.start_datetime


class NewsEventReminder(models.Model):
    """A reminder rule, e.g. 5 days before at 09:00 AM."""

    content = models.ForeignKey(
        NewsEvent,
        on_delete=models.CASCADE,
        related_name="reminder_rules",
    )
    days_before = models.PositiveSmallIntegerField(
        choices=REMINDER_DAY_CHOICES,
        validators=[MinValueValidator(1)],
        help_text="Number of days before the item's start/publish date and time.",
    )
    send_time = models.TimeField(
        default=time(9, 0),
        help_text="Local time of day when this reminder should be sent.",
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-days_before", "send_time")
        constraints = [
            models.UniqueConstraint(
                fields=("content", "days_before", "send_time"),
                name="unique_news_event_reminder_rule",
            ),
        ]

    def __str__(self):
        return f"{self.content.title} - {self.days_before} day(s) before"


class NewsEventDelivery(models.Model):
    """One scheduled delivery/timeline entry for a channel and delivery type.

    Create one row per channel (Email, In-app, or News Line). For the Event day
    timeline marker, use channel=SYSTEM. A row is retained after delivery so
    the reminder preview can show its actual delivery status.
    """

    class DeliveryType(models.TextChoices):
        ANNOUNCEMENT = "ANNOUNCEMENT", "Announcement"
        REMINDER = "REMINDER", "Reminder"
        EVENT_DAY = "EVENT_DAY", "Event day"
        EXPIRY = "EXPIRY", "Removal from Upcoming Events"

    class Channel(models.TextChoices):
        EMAIL = "EMAIL", "Email"
        IN_APP = "IN_APP", "In-app"
        NEWS_LINE = "NEWS_LINE", "News Line"
        SYSTEM = "SYSTEM", "System / timeline only"

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        PROCESSING = "PROCESSING", "Processing"
        SENT = "SENT", "Sent"
        FAILED = "FAILED", "Failed"
        SKIPPED = "SKIPPED", "Skipped"
        CANCELLED = "CANCELLED", "Cancelled"

    content = models.ForeignKey(
        NewsEvent,
        on_delete=models.CASCADE,
        related_name="delivery_schedules",
    )
    reminder_rule = models.ForeignKey(
        NewsEventReminder,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="delivery_records",
    )
    delivery_type = models.CharField(
        max_length=20,
        choices=DeliveryType.choices,
        db_index=True,
    )
    channel = models.CharField(
        max_length=12,
        choices=Channel.choices,
        default=Channel.IN_APP,
    )
    scheduled_for = models.DateTimeField(db_index=True)
    status = models.CharField(
        max_length=12,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )

    sent_at = models.DateTimeField(null=True, blank=True)
    last_attempt_at = models.DateTimeField(null=True, blank=True)
    attempt_count = models.PositiveSmallIntegerField(default=0)
    provider_message_id = models.CharField(max_length=255, blank=True)
    error_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("scheduled_for", "delivery_type", "channel")
        indexes = [
            models.Index(fields=("status", "scheduled_for")),
            models.Index(fields=("content", "scheduled_for")),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=("content", "delivery_type", "channel", "scheduled_for"),
                name="unique_news_event_delivery_slot",
            ),
        ]

    def __str__(self):
        return (
            f"{self.content.title} - {self.get_delivery_type_display()} - "
            f"{self.get_channel_display()} ({self.get_status_display()})"
        )


MAX_ATTACHMENT_SIZE = 10 * 1024 * 1024  # 10 MB, as shown in the reference form.
ALLOWED_ATTACHMENT_EXTENSIONS = ("pdf", "docx", "xlsx", "jpg", "jpeg", "png")


def validate_news_event_attachment_size(uploaded_file):
    if uploaded_file and uploaded_file.size > MAX_ATTACHMENT_SIZE:
        raise ValidationError("Each attachment must be 10 MB or smaller.")


def news_event_attachment_upload_to(instance, filename):
    safe_name = Path(filename).name
    content_id = instance.content_id or "draft"
    return f"news_events/{content_id}/{safe_name}"


class NewsEventAttachment(models.Model):
    """A separate row per uploaded document or image (supports multiple files)."""

    class AttachmentType(models.TextChoices):
        DOCUMENT = "DOCUMENT", "Document"
        IMAGE = "IMAGE", "Image"

    content = models.ForeignKey(
        NewsEvent,
        on_delete=models.CASCADE,
        related_name="attachments",
    )
    file = models.FileField(
        upload_to=news_event_attachment_upload_to,
        validators=[
            FileExtensionValidator(allowed_extensions=ALLOWED_ATTACHMENT_EXTENSIONS),
            validate_news_event_attachment_size,
        ],
    )
    attachment_type = models.CharField(
        max_length=10,
        choices=AttachmentType.choices,
        default=AttachmentType.DOCUMENT,
    )
    original_name = models.CharField(max_length=255, blank=True)
    caption = models.CharField(max_length=255, blank=True)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="uploaded_news_event_attachments",
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("uploaded_at",)

    def __str__(self):
        return self.original_name or Path(self.file.name).name

    def clean(self):
        super().clean()
        if not self.file:
            return

        extension = Path(self.file.name).suffix.lower().lstrip(".")
        document_extensions = {"pdf", "docx", "xlsx"}
        image_extensions = {"jpg", "jpeg", "png"}

        if self.attachment_type == self.AttachmentType.DOCUMENT:
            if extension not in document_extensions:
                raise ValidationError({
                    "file": "Documents must be PDF, DOCX, or XLSX files."
                })
        elif self.attachment_type == self.AttachmentType.IMAGE:
            if extension not in image_extensions:
                raise ValidationError({
                    "file": "Images must be JPG, JPEG, or PNG files."
                })

        if not self.original_name:
            self.original_name = Path(self.file.name).name


class NewsEventActivity(models.Model):
    """Audit trail for creation, scheduling, publishing, and other actions."""

    class Action(models.TextChoices):
        CREATED = "CREATED", "Created"
        UPDATED = "UPDATED", "Updated"
        SCHEDULED = "SCHEDULED", "Scheduled"
        PUBLISHED = "PUBLISHED", "Published"
        RESCHEDULED = "RESCHEDULED", "Rescheduled"
        CANCELLED = "CANCELLED", "Cancelled"
        ARCHIVED = "ARCHIVED", "Archived"
        REMINDER_SENT = "REMINDER_SENT", "Reminder sent"
        DELIVERY_FAILED = "DELIVERY_FAILED", "Delivery failed"

    content = models.ForeignKey(
        NewsEvent,
        on_delete=models.CASCADE,
        related_name="activity_logs",
    )
    action = models.CharField(max_length=20, choices=Action.choices, db_index=True)
    performed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="news_event_activity_logs",
    )
    note = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ("-created_at",)
        verbose_name = "News / Event Activity"
        verbose_name_plural = "News / Event Activities"

    def __str__(self):
        return f"{self.content.title} - {self.get_action_display()}"
