from django.contrib import admin

from .models import Notification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):

    list_display = (
        "notification_code",
        "title",
        "recipient",
        "sender",
        "module",
        "notification_type",
        "is_read",
        "created_at",
    )

    list_filter = (
        "module",
        "notification_type",
        "is_read",
        "created_at",
    )

    search_fields = (
        "notification_code",
        "title",
        "message",
        "recipient__username",
        "recipient__first_name",
        "recipient__last_name",
        "sender__username",
        "sender__first_name",
        "sender__last_name",
    )

    readonly_fields = (
        "notification_code",
        "created_at",
        "read_at",
    )

    ordering = (
        "-created_at",
    )

    date_hierarchy = "created_at"

    list_per_page = 25

    autocomplete_fields = (
        "company",
        "sender",
        "recipient",
    )

    fieldsets = (
        (
            "Notification Information",
            {
                "fields": (
                    "notification_code",
                    "company",
                    "module",
                    "notification_type",
                    "title",
                    "message",
                    "reference_id",
                    "action_url",
                )
            },
        ),
        (
            "Users",
            {
                "fields": (
                    "sender",
                    "recipient",
                )
            },
        ),
        (
            "Status",
            {
                "fields": (
                    "is_read",
                    "read_at",
                    "created_at",
                )
            },
        ),
    )