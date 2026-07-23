from django.conf import settings
from django.db import models
from django.db import transaction
from apps.companies.models import Company


class Notification(models.Model):

    class ModuleChoices(models.TextChoices):
        EMISSION = "EMISSION", "Emission"
        GOALS = "GOALS", "Goals & KPI"
        QUESTIONS = "QUESTIONS", "Questions"
        BRSR = "BRSR", "BRSR"

    class NotificationTypeChoices(models.TextChoices):
        ASSIGNED = "ASSIGNED", "Assigned"
        SUBMITTED = "SUBMITTED", "Submitted"
        APPROVED = "APPROVED", "Approved"
        REJECTED = "REJECTED", "Rejected"
        REMINDER = "REMINDER", "Reminder"
        OVERDUE = "OVERDUE", "Overdue"

    notification_code = models.CharField(
        max_length=20,
        unique=True,
        editable=False
    )

    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name="notifications"
    )

    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="sent_notifications"
    )

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="received_notifications"
    )

    module = models.CharField(
        max_length=30,
        choices=ModuleChoices.choices
    )

    notification_type = models.CharField(
        max_length=30,
        choices=NotificationTypeChoices.choices
    )

    title = models.CharField(
        max_length=255
    )

    message = models.TextField()

    reference_id = models.PositiveBigIntegerField(
        null=True,
        blank=True
    )

    action_url = models.CharField(
        max_length=500,
        blank=True,
        null=True
    )

    is_read = models.BooleanField(
        default=False
    )

    read_at = models.DateTimeField(
        null=True,
        blank=True
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    class Meta:
        db_table = "notifications"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.notification_code} - {self.title}"
    
    def save(self, *args, **kwargs):

        if not self.notification_code:

            with transaction.atomic():

                last_notification = (
                    Notification.objects
                    .select_for_update()
                    .order_by("-id")
                    .first()
                )

                if last_notification:
                    last_number = int(last_notification.notification_code.replace("NT", ""))
                    next_number = last_number + 1
                else:
                    next_number = 1

                self.notification_code = f"NT{next_number:06d}"

        super().save(*args, **kwargs)