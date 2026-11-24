from datetime import datetime, timedelta
import logging
from threading import Thread
from django.apps import apps
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.core.exceptions import ObjectDoesNotExist, PermissionDenied
from django.db import transaction
from django.db.models import Count, Q
from django.http import Http404, HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views import View
from django.views.generic import *
from .forms import *
from .models import *


logger = logging.getLogger(__name__)


def get_related_ids(user, relation_names):
    """Return IDs from a direct or many-to-many user relationship if present."""
    candidates = [user]
    for relation_name in ("profile", "userprofile", "employee"):
        try:
            related = getattr(user, relation_name, None)
        except ObjectDoesNotExist:
            related = None
        if related is not None:
            candidates.append(related)

    for candidate in candidates:
        for relation_name in relation_names:
            try:
                value = getattr(candidate, relation_name, None)
            except ObjectDoesNotExist:
                value = None
            if value is None:
                continue
            if hasattr(value, "values_list"):
                return list(value.values_list("pk", flat=True))
            if hasattr(value, "all"):
                return list(value.all().values_list("pk", flat=True))
            if getattr(value, "pk", None):
                return [value.pk]
            value_id = getattr(candidate, f"{relation_name}_id", None)
            if value_id:
                return [value_id]

    return []


def audience_scoped_news_events(queryset, user):
    """Apply the selected plant and department audience to feed queries.

    Recognized user relationships are ``plant`` / ``plants`` and
    ``department`` / ``departments`` on the user, profile, or employee record.
    If your User model uses different field names, update the two tuples below.
    """
    if user.is_superuser or getattr(user, "is_super_admin", False):
        return queryset.distinct()

    plant_ids = get_related_ids(user, ("plants", "plant", "assigned_plants"))
    department_ids = get_related_ids(
        user, ("departments", "department", "assigned_departments")
    )

    if plant_ids:
        queryset = queryset.filter(
            Q(all_plants=True) | Q(plants__in=plant_ids)
        )
    else:
        # Users without a plant assignment should still see items explicitly
        # targeted to every active plant, even when the author selected each
        # plant individually instead of checking the All plants option.
        plant_model_label = getattr(
            settings, "NEWS_EVENTS_PLANT_MODEL", "organizations.Plant"
        )
        plant_app, plant_model_name = plant_model_label.split(".", 1)
        plant_model = apps.get_model(plant_app, plant_model_name)
        active_plant_count = plant_model.objects.filter(is_active=True).count()
        plant_audience = Q(all_plants=True)
        if active_plant_count:
            queryset = queryset.annotate(
                _targeted_plant_count=Count("plants", distinct=True)
            )
            plant_audience |= Q(_targeted_plant_count__gte=active_plant_count)
        queryset = queryset.filter(plant_audience)

    if department_ids:
        queryset = queryset.filter(
            Q(departments__isnull=True) | Q(departments__in=department_ids)
        )
    else:
        queryset = queryset.filter(departments__isnull=True)

    return queryset.distinct()


def upcoming_event_queryset(queryset, now=None):
    """Include all future events and those active through their end/start date."""
    now = now or timezone.now()
    return queryset.filter(
        Q(start_datetime__gt=now)
        | Q(end_datetime__gte=now)
        | Q(
            end_datetime__isnull=True,
            start_datetime__date__gte=timezone.localdate(now),
        )
    )


def record_activity(content, action, user=None, note="", metadata=None):
    """Write an audit record for a News/Event action."""
    return NewsEventActivity.objects.create(
        content=content,
        action=action,
        performed_by=user if getattr(user, "is_authenticated", False) else None,
        note=note,
        metadata=metadata or {},
    )


def _aware_datetime(day, send_time):
    """Combine a date and configured local send time using Django's timezone."""
    value = datetime.combine(day, send_time)
    if timezone.is_aware(timezone.now()):
        return timezone.make_aware(value, timezone.get_current_timezone())
    return value


def _create_delivery(content, delivery_type, channel, scheduled_for, reminder_rule=None):
    """Create/update a delivery slot without duplicating an existing slot."""
    now = timezone.now()
    # Announcement slots are due immediately when their publication time is
    # now or in the past. Only missed reminders should be skipped.
    status = (
        NewsEventDelivery.Status.SKIPPED
        if (
            scheduled_for < now
            and delivery_type == NewsEventDelivery.DeliveryType.REMINDER
        )
        else NewsEventDelivery.Status.PENDING
    )
    defaults = {"status": status, "reminder_rule": reminder_rule}
    if status == NewsEventDelivery.Status.SKIPPED:
        defaults["error_message"] = "The scheduled delivery time has already passed."

    delivery, created = NewsEventDelivery.objects.get_or_create(
        content=content,
        delivery_type=delivery_type,
        channel=channel,
        scheduled_for=scheduled_for,
        defaults=defaults,
    )
    if not created and delivery.status in {
        NewsEventDelivery.Status.CANCELLED,
        NewsEventDelivery.Status.SKIPPED,
    }:
        delivery.status = status
        delivery.reminder_rule = reminder_rule
        delivery.error_message = defaults.get("error_message", "")
        delivery.save(update_fields=["status", "reminder_rule", "error_message", "updated_at"])

    return delivery


def send_published_announcement_now(content):
    """Start due announcement delivery in the background for any item type."""
    now = timezone.now()
    delivery = content.delivery_schedules.filter(
        delivery_type=NewsEventDelivery.DeliveryType.ANNOUNCEMENT,
        channel=NewsEventDelivery.Channel.EMAIL,
        status=NewsEventDelivery.Status.PENDING,
        scheduled_for__lte=now,
    ).order_by("scheduled_for", "pk").first()
    if not delivery:
        return False

    try:
        # This immediate-publish path must not depend on a running Celery
        # worker. The task's conditional DB claim prevents duplicate sending
        # if the periodic Celery dispatcher picks up the same row.
        from .tasks import run_email_delivery_in_background

        Thread(
            target=run_email_delivery_in_background,
            args=(delivery.pk,),
            name=f"news-event-email-{delivery.pk}",
            daemon=True,
        ).start()
        return True
    except Exception as exc:
        logger.warning(
            "Could not start background News/Event delivery %s: %s",
            delivery.pk,
            exc,
        )
        return False


def refresh_delivery_schedules(content):
    """Rebuild pending delivery rows after a News/Event is saved.

    Existing SENT/PROCESSING/FAILED rows are retained as delivery history.
    Obsolete PENDING rows are cancelled before replacement slots are created.
    A worker must later claim PENDING rows whose ``scheduled_for`` is due.
    """
    NewsEventDelivery.objects.filter(
        content=content,
        status=NewsEventDelivery.Status.PENDING,
    ).update(
        status=NewsEventDelivery.Status.CANCELLED,
        error_message="Schedule refreshed after News/Event changes.",
        updated_at=timezone.now(),
    )

    if content.status not in (NewsEvent.Status.PUBLISHED, NewsEvent.Status.SCHEDULED):
        return
    now = timezone.now()
    if content.is_event:
        announcement_time = content.published_at or now
    elif content.status == NewsEvent.Status.SCHEDULED and content.start_datetime:
        announcement_time = max(content.start_datetime, now)
    else:
        announcement_time = content.published_at or now

    if content.send_email:
        _create_delivery(
            content,
            NewsEventDelivery.DeliveryType.ANNOUNCEMENT,
            NewsEventDelivery.Channel.EMAIL,
            announcement_time,
        )
    if content.send_in_app:
        _create_delivery(
            content,
            NewsEventDelivery.DeliveryType.ANNOUNCEMENT,
            NewsEventDelivery.Channel.IN_APP,
            announcement_time,
        )
    if content.show_in_news_line:
        _create_delivery(
            content,
            NewsEventDelivery.DeliveryType.ANNOUNCEMENT,
            NewsEventDelivery.Channel.NEWS_LINE,
            announcement_time,
        )

    if content.start_datetime:
        for rule in content.reminder_rules.filter(is_active=True):
            reminder_day = timezone.localtime(content.start_datetime).date() - timedelta(
                days=rule.days_before
            )
            reminder_datetime = _aware_datetime(reminder_day, rule.send_time)
            channels = []
            if content.send_email:
                channels.append(NewsEventDelivery.Channel.EMAIL)
            if content.send_in_app:
                channels.append(NewsEventDelivery.Channel.IN_APP)
            for channel in channels:
                _create_delivery(
                    content,
                    NewsEventDelivery.DeliveryType.REMINDER,
                    channel,
                    reminder_datetime,
                    reminder_rule=rule,
                )

    if content.is_event and content.start_datetime:
        _create_delivery(
            content,
            NewsEventDelivery.DeliveryType.EVENT_DAY,
            NewsEventDelivery.Channel.SYSTEM,
            content.start_datetime,
        )

        _create_delivery(
            content,
            NewsEventDelivery.DeliveryType.EXPIRY,
            NewsEventDelivery.Channel.SYSTEM,
            content.auto_remove_at,
        )


def cancel_pending_deliveries(content, reason):
    NewsEventDelivery.objects.filter(
        content=content,
        status=NewsEventDelivery.Status.PENDING,
    ).update(
        status=NewsEventDelivery.Status.CANCELLED,
        error_message=reason,
        updated_at=timezone.now(),
    )


# Permission mixin
class NewsEventPermissionRequiredMixin(PermissionRequiredMixin):
    """Support Django permissions and role.permissions M2M permissions."""

    raise_exception = True

    def has_permission(self):
        user = self.request.user
        if not user.is_authenticated:
            return False
        if user.is_superuser:
            return True
        if super().has_permission():
            return True

        required = self.get_permission_required()
        role = getattr(user, "role", None)
        role_permissions = getattr(role, "permissions", None) if role else None
        if role_permissions is None:
            return False

        try:
            assigned_permissions = role_permissions.all()
        except (AttributeError, TypeError):
            return False

        assigned = set()
        for permission in assigned_permissions:
            codename = getattr(permission, "codename", None) or getattr(
                permission, "code", None
            )
            content_type = getattr(permission, "content_type", None)
            app_label = getattr(content_type, "app_label", None)
            if codename and app_label:
                assigned.add(f"{app_label}.{codename}")
            elif codename:
                assigned.add(codename)

        return all(
            permission in assigned or permission.rsplit(".", 1)[-1] in assigned
            for permission in required
        )


class NewsEventAudienceQuerysetMixin:
    """Apply plant and department audience scoping to user-facing pages."""

    def get_queryset(self):
        queryset = super().get_queryset()
        return audience_scoped_news_events(queryset, self.request.user)


# List and feed views
class NewsEventListView(LoginRequiredMixin, NewsEventPermissionRequiredMixin, ListView,):
    """Management list for news and events across the selected plants."""

    model = NewsEvent
    permission_required = "news_feed.view_newsevent"
    template_name = "news_events/news_event_list.html"
    context_object_name = "news_events"
    paginate_by = 20

    def get_queryset(self):
        queryset = super().get_queryset().select_related(
            "created_by", "updated_by"
        ).prefetch_related("plants", "departments", "attachments")

        search = self.request.GET.get("q", "").strip()
        item_type = self.request.GET.get("type", "").strip().lower()
        status = self.request.GET.get("status", "").strip().upper()

        if search:
            queryset = queryset.filter(
                Q(title__icontains=search) | Q(description__icontains=search)
            )
        if item_type == "news":
            queryset = queryset.filter(is_event=False)
        elif item_type == "event":
            queryset = queryset.filter(is_event=True)
        if status in NewsEvent.Status.values:
            queryset = queryset.filter(status=status)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        base_queryset = NewsEvent.objects.all()
        context["total_items"] = base_queryset.count()
        context["news_count"] = base_queryset.filter(is_event=False).count()
        context["event_count"] = base_queryset.filter(is_event=True).count()
        context["scheduled_count"] = base_queryset.filter(
            status=NewsEvent.Status.SCHEDULED
        ).count()
        context["published_count"] = base_queryset.filter(
            status=NewsEvent.Status.PUBLISHED
        ).count()
        context["draft_count"] = base_queryset.filter(
            status=NewsEvent.Status.DRAFT
        ).count()
        context["cancelled_count"] = base_queryset.filter(
            status=NewsEvent.Status.CANCELLED
        ).count()
        return context


class NewsEventFeedView(LoginRequiredMixin,NewsEventAudienceQuerysetMixin,ListView,):
    """User-facing feed for upcoming and recently expired News/Events."""

    model = NewsEvent
    template_name = "news_events/news_event_feed.html"
    context_object_name = "news_events"
    paginate_by = 15

    def get_queryset(self):
        now = timezone.now()
        today = timezone.localdate(now)

        feed_mode = self.request.GET.get("feed", "upcoming").lower()
        search = self.request.GET.get("q", "").strip()

        queryset = NewsEvent.objects.filter(
            status__in=[
                NewsEvent.Status.PUBLISHED,
                NewsEvent.Status.SCHEDULED,
            ]
        )

        if feed_mode == "expired":
            cutoff = now - timedelta(days=180)

            expired_news = Q(
                is_event=False,
                status=NewsEvent.Status.PUBLISHED,
                end_datetime__gte=cutoff,
                end_datetime__lt=now,
            )

            expired_events = Q(
                is_event=True,
                end_datetime__gte=cutoff,
                end_datetime__lt=now,
            ) | Q(
                is_event=True,
                end_datetime__isnull=True,
                start_datetime__date__gte=cutoff.date(),
                start_datetime__date__lt=today,
            )

            queryset = queryset.filter(
                expired_news | expired_events
            )

        else:
            visible_news = (
                Q(
                    is_event=False,
                    status=NewsEvent.Status.PUBLISHED,
                )
                & (
                    Q(published_at__isnull=True)
                    | Q(published_at__lte=now)
                )
                & (
                    Q(end_datetime__isnull=True)
                    | Q(end_datetime__gte=now)
                )
            ) | Q(
                is_event=False,
                status=NewsEvent.Status.SCHEDULED,
                start_datetime__gte=now,
            )

            visible_events = Q(
                is_event=True,
                status__in=[
                    NewsEvent.Status.PUBLISHED,
                    NewsEvent.Status.SCHEDULED,
                ],
            ) & (
                Q(start_datetime__gt=now)
                | Q(end_datetime__gte=now)
                | Q(
                    end_datetime__isnull=True,
                    start_datetime__date__gte=today,
                )
            )

            queryset = queryset.filter(
                visible_news | visible_events
            )

        queryset = audience_scoped_news_events(
            queryset,
            self.request.user,
        )

        if search:
            queryset = queryset.filter(
                Q(title__icontains=search)
                | Q(description__icontains=search)
            )

        return queryset.select_related(
            "created_by"
        ).prefetch_related(
            "plants",
            "departments",
            "attachments",
        ).order_by(
            "-end_datetime",
            "-start_datetime",
            "-published_at",
            "-created_at",
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context["feed_mode"] = self.request.GET.get(
            "feed", "upcoming"
        ).lower()

        context["upcoming_events"] = audience_scoped_news_events(
            upcoming_event_queryset(
                NewsEvent.objects.filter(
                    is_event=True,
                    status__in=[
                        NewsEvent.Status.PUBLISHED,
                        NewsEvent.Status.SCHEDULED,
                    ],
                )
            ),
            self.request.user,
        ).select_related(
            "created_by"
        ).prefetch_related(
            "plants",
            "departments",
            "attachments",
        ).order_by("start_datetime")[:5]

        return context


class UpcomingEventsListView(LoginRequiredMixin, NewsEventAudienceQuerysetMixin, ListView,):
    model = NewsEvent
    template_name = "news_events/upcoming_events.html"
    context_object_name = "upcoming_events"
    paginate_by = 20

    def get_queryset(self):
        return (
            upcoming_event_queryset(
                super().get_queryset().filter(
                    is_event=True,
                    status__in=[
                        NewsEvent.Status.PUBLISHED,
                        NewsEvent.Status.SCHEDULED,
                    ],
                )
            )
            .select_related("created_by")
            .prefetch_related("plants", "departments", "attachments")
            .order_by("start_datetime")
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        now = timezone.now()
        news = NewsEvent.objects.filter(is_event=False).filter(
            (
                Q(status=NewsEvent.Status.PUBLISHED)
                & (Q(published_at__isnull=True) | Q(published_at__lte=now))
            )
            | Q(
                status=NewsEvent.Status.SCHEDULED,
                start_datetime__gte=now,
            )
        ).filter(
            Q(end_datetime__isnull=True) | Q(end_datetime__gte=now)
        )
        context["news_items"] = audience_scoped_news_events(
            news, self.request.user
        ).prefetch_related("plants", "departments", "attachments").order_by(
            "-published_at", "-created_at"
        )[:10]
        return context


# Detail view
class NewsEventDetailView(LoginRequiredMixin, NewsEventPermissionRequiredMixin, DetailView,):
    model = NewsEvent
    permission_required = "news_feed.view_newsevent"
    template_name = "news_events/news_event_detail.html"
    context_object_name = "news_event"

    def get_queryset(self):
        return super().get_queryset().select_related(
            "created_by", "updated_by", "published_by"
        ).prefetch_related(
            "plants",
            "departments",
            "attachments",
            "reminder_rules",
            "delivery_schedules",
            "activity_logs__performed_by",
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["reminder_rules"] = self.object.reminder_rules.all()
        context["delivery_schedules"] = self.object.delivery_schedules.all()
        context["activity_logs"] = self.object.activity_logs.select_related(
            "performed_by"
        )
        return context



class NewsEventPublicDetailView(LoginRequiredMixin, DetailView):
    """Read-only detail page for published News/Events, including expired items."""

    login_url = reverse_lazy("accounts:login")
    model = NewsEvent
    template_name = "news_events/news_event_public_detail.html"
    context_object_name = "news_event"

    def get_queryset(self):
        now = timezone.now()

        # Allow published news even if its end date has passed.
        visible_news = (
            Q(is_event=False, status=NewsEvent.Status.PUBLISHED)
            & (Q(published_at__isnull=True) | Q(published_at__lte=now))
        ) | Q(
            is_event=False,
            status=NewsEvent.Status.SCHEDULED,
            start_datetime__gte=now,
        )

        # Allow published and scheduled events, including expired events.
        visible_events = Q(
            is_event=True,
            status__in=[
                NewsEvent.Status.PUBLISHED,
                NewsEvent.Status.SCHEDULED,
            ],
        )

        queryset = NewsEvent.objects.filter(visible_news | visible_events)

        # Continue enforcing plant and department audience restrictions.
        return audience_scoped_news_events(
            queryset, self.request.user
        ).select_related(
            "created_by"
        ).prefetch_related(
            "plants",
            "departments",
            "attachments",
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        news_event = self.object
        now = timezone.now()

        is_expired = False

        if news_event.end_datetime:
            is_expired = news_event.end_datetime < now

        elif news_event.is_event and news_event.start_datetime:
            is_expired = (
                news_event.start_datetime.date() < timezone.localdate(now)
            )

        context["is_expired"] = is_expired

        return context

# Create and update views with reminder choices and multiple file upload
class NewsEventMultiFormProcessingMixin:
    """Process the main ModelForm, reminder choices, and files together."""
    is_update_view = False
    success_message = "News/Event saved successfully."

    def get_attachment_form(self, *, data=None, files=None):
        return NewsEventAttachmentUploadForm(data=data, files=files)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.setdefault("attachment_form", self.get_attachment_form())
        return context

    def post(self, request, *args, **kwargs):
        # Status is an action button, not a user-editable field. Keep the
        # actual model field hidden and translate the selected action here.
        post_data = request.POST.copy()
        action = post_data.get("action")
        if action == "schedule":
            post_data["status"] = NewsEvent.Status.SCHEDULED
        elif action == "save_draft":
            post_data["status"] = NewsEvent.Status.DRAFT
        request.POST = post_data

        if self.is_update_view:
            self.object = self.get_object()
            old_status = self.object.status
        else:
            self.object = None
            old_status = None

        form = self.get_form()
        attachment_form = self.get_attachment_form(
            data=request.POST,
            files=request.FILES,
        )

        form_is_valid = form.is_valid()
        attachments_are_valid = attachment_form.is_valid()

        if form_is_valid and attachments_are_valid:
            return self.forms_valid(
                form,
                attachment_form,
                old_status=old_status,
            )

        return self.forms_invalid(form, attachment_form)

    def forms_valid(self, form, attachment_form, *, old_status=None):
        user = self.request.user
        is_new = self.object is None

        with transaction.atomic():
            self.object = form.save(commit=False)

            self.object.send_in_app = True
            self.object.show_in_news_line = True

            if is_new:
                self.object.created_by = user
            self.object.updated_by = user

            if self.object.status == NewsEvent.Status.PUBLISHED:
                if old_status != NewsEvent.Status.PUBLISHED:
                    self.object.published_at = timezone.now()
                    self.object.published_by = user
                elif not self.object.published_at:
                    self.object.published_at = timezone.now()
                    self.object.published_by = user

            self.object.full_clean()
            self.object.save()
            form.save_m2m()

            # Replace reminder rules from the event creation/edit selections.
            self.object.reminder_rules.all().delete()
            if self.object.is_event:
                send_time = datetime.strptime(
                    form.cleaned_data.get("reminder_send_time") or "09:00",
                    "%H:%M",
                ).time()
                NewsEventReminder.objects.bulk_create([
                    NewsEventReminder(
                        content=self.object,
                        days_before=int(days),
                        send_time=send_time,
                        is_active=True,
                    )
                    for days in form.cleaned_data.get("reminder_days", [])
                ])

            attachment_form.save_attachments(
                self.object,
                uploaded_by=user,
            )

            if self.object.status in (
                NewsEvent.Status.PUBLISHED,
                NewsEvent.Status.SCHEDULED,
            ):
                refresh_delivery_schedules(self.object)
            else:
                cancel_pending_deliveries(
                    self.object,
                    "News/Event is not currently scheduled for delivery.",
                )

            if is_new:
                record_activity(
                    self.object,
                    NewsEventActivity.Action.CREATED,
                    user,
                    note="News/Event created.",
                )
            else:
                record_activity(
                    self.object,
                    NewsEventActivity.Action.UPDATED,
                    user,
                    note="News/Event details updated.",
                )

            if self.object.status == NewsEvent.Status.SCHEDULED and old_status != NewsEvent.Status.SCHEDULED:
                record_activity(
                    self.object,
                    NewsEventActivity.Action.SCHEDULED,
                    user,
                    note="News/Event delivery schedule configured.",
                )
            elif self.object.status == NewsEvent.Status.PUBLISHED and old_status != NewsEvent.Status.PUBLISHED:
                record_activity(
                    self.object,
                    NewsEventActivity.Action.PUBLISHED,
                    user,
                    note="News/Event published.",
                )

        if (
            self.object.status == NewsEvent.Status.PUBLISHED
            and old_status != NewsEvent.Status.PUBLISHED
        ):
            if self.object.send_email:
                queued = send_published_announcement_now(self.object)
                self.success_message = (
                    "News/Event published successfully. Email notification "
                    + (
                        "queued for background delivery."
                        if queued
                        else "will be processed."
                    )
                )

        messages.success(self.request, self.success_message)
        return HttpResponseRedirect(self.get_success_url())

    def forms_invalid(self, form, attachment_form):
        messages.error(self.request, "Please correct the errors below.")
        return self.render_to_response(
            self.get_context_data(
                form=form,
                attachment_form=attachment_form,
            )
        )

    def get_success_url(self):
        return reverse(
            "news_events:news_event_detail",
            kwargs={"pk": self.object.pk},
        )


class NewsEventCreateView(LoginRequiredMixin, NewsEventPermissionRequiredMixin, NewsEventMultiFormProcessingMixin, CreateView,):
    model = NewsEvent
    form_class = NewsEventForm
    permission_required = "news_feed.add_newsevent"
    template_name = "news_events/news_event_form.html"
    is_update_view = False
    success_message = "News/Event created successfully."


class NewsEventUpdateView(LoginRequiredMixin, NewsEventPermissionRequiredMixin, NewsEventMultiFormProcessingMixin, UpdateView,):
    model = NewsEvent
    form_class = NewsEventForm
    permission_required = "news_feed.change_newsevent"
    template_name = "news_events/news_event_form.html"
    is_update_view = True
    success_message = "News/Event updated successfully."

    def get_queryset(self):
        return super().get_queryset().exclude(status=NewsEvent.Status.ARCHIVED)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["existing_attachments"] = self.object.attachments.all()
        return context


# Publish, archive, cancel, and delete actions
class NewsEventStatusActionView(LoginRequiredMixin, NewsEventPermissionRequiredMixin, View,):
    """Base POST-only status action for one News/Event."""

    model = NewsEvent
    permission_required = "news_feed.change_newsevent"
    success_message = "News/Event status updated."

    def post(self, request, *args, **kwargs):
        content = get_object_or_404(self.get_queryset(), pk=kwargs.get("pk"))
        self.apply_action(content, request.user)
        messages.success(request, self.success_message)
        return redirect("news_events:news_event_detail", pk=content.pk)

    def get_queryset(self):
        return NewsEvent.objects.all()

    def apply_action(self, content, user):
        raise NotImplementedError


class PublishNewsEventView(NewsEventStatusActionView):
    success_message = "News/Event published successfully."

    def post(self, request, *args, **kwargs):
        content = get_object_or_404(NewsEvent.objects.all(), pk=kwargs.get("pk"))
        if content.status != NewsEvent.Status.SCHEDULED:
            messages.error(
                request,
                "This News/Event must be saved or scheduled before it can be published.",
            )
            return redirect("news_events:news_event_detail", pk=content.pk)
        return super().post(request, *args, **kwargs)

    def apply_action(self, content, user):
        # Keep the state transition guarded here too, even if the action is
        # invoked from another code path that bypasses the POST check.
        if content.status != NewsEvent.Status.SCHEDULED:
            raise PermissionDenied(
                "Only scheduled News/Events can be published directly."
            )

        with transaction.atomic():
            content.status = NewsEvent.Status.PUBLISHED
            content.published_at = timezone.now()
            content.published_by = user
            content.updated_by = user
            content.save(
                update_fields=[
                    "status",
                    "published_at",
                    "published_by",
                    "updated_by",
                    "updated_at",
                ]
            )
            refresh_delivery_schedules(content)
            record_activity(
                content,
                NewsEventActivity.Action.PUBLISHED,
                user,
                note="News/Event manually published.",
            )

        if content.send_email:
            queued = send_published_announcement_now(content)
            self.success_message = (
                "News/Event published successfully. Email notification "
                + (
                    "queued for background delivery."
                    if queued
                    else "will be processed."
                )
            )


class ArchiveNewsEventView(NewsEventStatusActionView):
    success_message = "News/Event archived successfully."

    def apply_action(self, content, user):
        if content.status == NewsEvent.Status.ARCHIVED:
            raise PermissionDenied("This News/Event is already archived.")
        with transaction.atomic():
            content.archived_from_status = content.status
            content.status = NewsEvent.Status.ARCHIVED
            content.archived_at = timezone.now()
            content.updated_by = user
            content.save(
                update_fields=[
                    "status", "archived_at", "archived_from_status",
                    "updated_by", "updated_at",
                ]
            )
            cancel_pending_deliveries(content, "News/Event archived.")
            record_activity(
                content,
                NewsEventActivity.Action.ARCHIVED,
                user,
                note="News/Event archived.",
            )


class CancelNewsEventView(NewsEventStatusActionView):
    success_message = "News/Event cancelled successfully."

    def apply_action(self, content, user):
        if content.status == NewsEvent.Status.ARCHIVED:
            raise PermissionDenied("Restore this News/Event before cancelling it.")
        with transaction.atomic():
            content.status = NewsEvent.Status.CANCELLED
            content.updated_by = user
            content.save(update_fields=["status", "updated_by", "updated_at"])
            cancel_pending_deliveries(content, "News/Event cancelled.")
            record_activity(
                content,
                NewsEventActivity.Action.CANCELLED,
                user,
                note="News/Event cancelled.",
            )


class RestoreNewsEventView(NewsEventStatusActionView):
    success_message = "News/Event restored successfully."

    def apply_action(self, content, user):
        if content.status != NewsEvent.Status.ARCHIVED:
            raise PermissionDenied("Only archived News/Events can be restored.")

        with transaction.atomic():
            restore_status = content.archived_from_status
            if restore_status not in {
                NewsEvent.Status.DRAFT,
                NewsEvent.Status.SCHEDULED,
                NewsEvent.Status.PUBLISHED,
                NewsEvent.Status.CANCELLED,
            }:
                # Older archived records predate archived_from_status.
                restore_status = (
                    NewsEvent.Status.PUBLISHED
                    if content.published_at
                    else NewsEvent.Status.SCHEDULED
                    if content.start_datetime
                    else NewsEvent.Status.DRAFT
                )

            content.status = restore_status
            content.archived_at = None
            content.archived_from_status = None
            content.updated_by = user
            content.save(
                update_fields=[
                    "status", "archived_at", "archived_from_status",
                    "updated_by", "updated_at",
                ]
            )

            if restore_status in (
                NewsEvent.Status.PUBLISHED,
                NewsEvent.Status.SCHEDULED,
            ):
                refresh_delivery_schedules(content)
            else:
                cancel_pending_deliveries(
                    content,
                    "Restored News/Event remains a draft.",
                )

            record_activity(
                content,
                NewsEventActivity.Action.UPDATED,
                user,
                note=f"News/Event restored to {content.get_status_display()}.",
            )


class NewsEventDeleteView(LoginRequiredMixin, NewsEventPermissionRequiredMixin, DeleteView,):
    model = NewsEvent
    permission_required = "news_feed.delete_newsevent"
    template_name = "news_events/news_event_confirm_delete.html"
    success_url = reverse_lazy("news_events:news_event_list")
    context_object_name = "news_event"

    def get_queryset(self):
        return super().get_queryset().exclude(status=NewsEvent.Status.ARCHIVED)

    def form_valid(self, form):
        messages.success(self.request, "News/Event deleted successfully.")
        return super().form_valid(form)


# Attachment delete action
class NewsEventAttachmentDeleteView(LoginRequiredMixin, NewsEventPermissionRequiredMixin, View,):
    permission_required = "news_feed.change_newsevent"

    def post(self, request, *args, **kwargs):
        attachment = get_object_or_404(
            NewsEventAttachment.objects.select_related("content"),
            pk=kwargs.get("attachment_pk"),
        )
        content = get_object_or_404(
            NewsEvent.objects.all(),
            pk=attachment.content_id,
        )

        if content.status == NewsEvent.Status.ARCHIVED:
            messages.error(request, "Restore this News/Event before changing its attachments.")
            return redirect("news_events:news_event_detail", pk=content.pk)

        if attachment.file:
            attachment.file.delete(save=False)
        attachment.delete()
        record_activity(
            content,
            NewsEventActivity.Action.UPDATED,
            request.user,
            note="An attachment was removed.",
        )
        messages.success(request, "Attachment removed successfully.")
        return redirect("news_events:news_event_detail", pk=content.pk)




