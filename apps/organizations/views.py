from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import ListView, CreateView, UpdateView, DeleteView, TemplateView,DetailView
from django.urls import reverse_lazy
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.utils import timezone
from datetime import timedelta
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.views import View
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect
from django.db.models import Q, Count
# from apps.accounts.views import AdminRequiredMixin
from django.http import JsonResponse
from django.views import View
from .models import *
from .forms import *
from django.forms import ValidationError
from .models import Plant
from django.db.models import F
from django.db.models.functions import Cast,Substr
from django.db.models import IntegerField
from django.db.models.functions import Lower
from django.db.models import Case, When, IntegerField, Value
from django.db.models.functions import Cast, Substr
from .models import FinancialYear
from .forms import FinancialYearForm
from django.db import transaction
from apps.companies.models import Company
from .workflow_configuration_engine import WorkflowConfigurationEngine
from apps.news_feed.models import *
from apps.news_feed.views import (audience_scoped_news_events, upcoming_event_queryset)

class CanAccessOrganizationMixin(UserPassesTestMixin):

    def test_func(self):
        user = self.request.user

        if not user.is_authenticated:
            return False

        if user.is_superuser:
            return True

        if not user.role:
            return False

        return user.role.permissions.filter(code="ACCESS_ORGANIZATIONS_MODULE").exists()

    def get_allowed_plants(self):
        user = self.request.user

        if user.is_superuser:
            return Plant.objects.all()

        if getattr(user, 'is_super_admin', False):
            return Plant.objects.all()

        if user.role and user.role.role_code == 'COMPANYADMIN':
            return Plant.objects.filter(created_by__company=user.company).distinct()

        return user.assigned_plants.filter(is_active=True)

    def handle_no_permission(self):
        messages.error(self.request, 'You do not have permission to access this module.')
        return redirect('accounts:dashboard')


# ==================== PLANT VIEWS ====================
class PlantListView(LoginRequiredMixin, CanAccessOrganizationMixin, ListView):
    """List all plants"""
    model = Plant
    template_name = 'organizations/plant_list.html'
    context_object_name = 'plants'
    paginate_by = 20
    
    def get_queryset(self):
        user = self.request.user
        if user.is_superuser or user.role.role_code == 'SUPERADMIN':
            queryset = Plant.objects.all()
        else:
            if user.company:
                queryset = Plant.objects.filter(Q(created_by=user) | Q(created_by__company=user.company)).distinct()
            else:
                queryset = Plant.objects.filter(created_by=user)
        
        # Search
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) |
                Q(code__icontains=search) |
                Q(country__name__icontains=search) |
                Q(state__name__icontains=search) |
                Q(city__name__icontains=search)
            )
        
        # Filter by status
        status = self.request.GET.get('status')
        if status == 'active':
            queryset = queryset.filter(is_active=True)
        elif status == 'inactive':
            queryset = queryset.filter(is_active=False)
        
        return queryset.order_by('name')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search_query'] = self.request.GET.get('search', '')
        context['selected_status'] = self.request.GET.get('status', '')
        return context

class PlantCreateView(LoginRequiredMixin, CanAccessOrganizationMixin, CreateView):
    """Create new plant"""
    model = Plant
    form_class = PlantForm
    template_name = 'organizations/plant_form.html'
    success_url = reverse_lazy('organizations:plant_list')
    
    def form_valid(self, form):
        form.instance.created_by = self.request.user
        messages.success(self.request, f'Plant {form.instance.name} created successfully!')
        return super().form_valid(form)


class PlantUpdateView(LoginRequiredMixin, CanAccessOrganizationMixin, UpdateView):
    """Update plant"""
    model = Plant
    form_class = PlantForm
    template_name = 'organizations/plant_form.html'
    success_url = reverse_lazy('organizations:plant_list')
    
    def form_valid(self, form):
        messages.success(self.request, f'Plant {form.instance.name} updated successfully!')
        return super().form_valid(form)


class PlantDeleteView(LoginRequiredMixin, CanAccessOrganizationMixin,  DeleteView):
    """Delete plant"""
    model = Plant
    template_name = 'organizations/plant_confirm_delete.html'
    success_url = reverse_lazy('organizations:plant_list')
    
    def delete(self, request, *args, **kwargs):
        plant = self.get_object()
        messages.success(request, f'Plant {plant.name} deleted successfully!')
        return super().delete(request, *args, **kwargs)

class FinancialYearListView(LoginRequiredMixin, ListView):
    model = FinancialYear
    template_name = "organizations/financial_years/financial_year_list.html"
    context_object_name = "financial_years"
    paginate_by = 10

    def get_queryset(self):
        queryset = FinancialYear.objects.all().order_by("-start_date")

        search = self.request.GET.get("search")

        if search:
            queryset = queryset.filter(
                Q(financial_year__icontains=search)
            )

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["search_query"] = self.request.GET.get("search", "")
        return context

from datetime import date
class FinancialYearCreateView(LoginRequiredMixin, CreateView):
    model = FinancialYear
    form_class = FinancialYearForm
    template_name = "organizations/financial_years/financial_year_form.html"
    success_url = reverse_lazy("organizations:financial_year_list")

    def get_initial(self):
        initial = super().get_initial()

        today = date.today()

        if today.month >= 4:
            start_year = today.year
        else:
            start_year = today.year - 1

        initial["financial_year"] = (
            f"{start_year}-{start_year + 1}"
        )

        return initial

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Create Financial Year"
        return context

    def form_valid(self, form):
        with transaction.atomic():
            form.save()

        messages.success(
            self.request,
            "Financial Year created successfully."
        )

        return redirect(self.success_url)

    def form_invalid(self, form):
        print(form.errors)
        return super().form_invalid(form)
    
class FinancialYearUpdateView(LoginRequiredMixin, UpdateView):
    model = FinancialYear
    form_class = FinancialYearForm
    template_name = "organizations/financial_years/financial_year_form.html"
    success_url = reverse_lazy("organizations:financial_year_list")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Edit Financial Year"
        return context

    def form_valid(self, form):
        with transaction.atomic():
            form.save()

        messages.success(
            self.request,
            "Financial Year updated successfully."
        )

        return redirect(self.success_url)

    def form_invalid(self, form):
        print(form.errors)
        return super().form_invalid(form)

class CalendarWeekView(LoginRequiredMixin, TemplateView):
    template_name = "organizations/calendar.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        now = timezone.now()
        today = timezone.localdate(now)

        # Fetch published and scheduled upcoming events
        queryset = NewsEvent.objects.filter(
            is_event=True,
            status__in=[
                NewsEvent.Status.PUBLISHED,
                NewsEvent.Status.SCHEDULED,
            ],
        )

        # Include future events and currently active events
        queryset = upcoming_event_queryset(queryset, now)

        # Apply plant and department audience restrictions
        queryset = audience_scoped_news_events(
            queryset,
            self.request.user,
        )

        queryset = queryset.select_related(
            "created_by"
        ).prefetch_related(
            "plants",
            "departments",
        ).order_by("start_datetime")

        calendar_events = {}

        for event in queryset:
            if not event.start_datetime:
                continue

            start_date = timezone.localtime(event.start_datetime).date()

            end_date = (
                timezone.localtime(event.end_datetime).date()
                if event.end_datetime
                else start_date
            )

            display_start = max(start_date, today)

            current_date = display_start

            while current_date <= end_date:
                date_key = current_date.strftime("%Y-%m-%d")

                calendar_events.setdefault(date_key, []).append({
                    "id": event.pk,
                    "title": event.title,
                    "desc": event.description or "",
                    "focus": "Upcoming Event",
                    "category": "upcoming",
                    "icon": "📅",
                    "status": event.get_status_display(),
                    "url": f"/news_feed/view/{event.pk}/",
                    "start": timezone.localtime(event.start_datetime).strftime("%I:%M %p"),
                    "end": (
                        timezone.localtime(event.end_datetime).strftime("%I:%M %p")
                        if event.end_datetime
                        else ""
                    ),
                })

                current_date += timedelta(days=1)

        # Scheduled news and published news that remains active are also
        # represented on the calendar, on their publish date through expiry.
        news_queryset = NewsEvent.objects.filter(is_event=False).filter(
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
        news_queryset = audience_scoped_news_events(
            news_queryset, self.request.user
        ).select_related("created_by").prefetch_related("plants", "departments")

        for news_item in news_queryset:
            occurrence_datetime = (
                news_item.start_datetime
                if news_item.status == NewsEvent.Status.SCHEDULED
                else news_item.published_at
                or news_item.start_datetime
                or news_item.created_at
            )
            if not occurrence_datetime:
                continue

            start_date = timezone.localtime(occurrence_datetime).date()
            end_date = (
                timezone.localtime(news_item.end_datetime).date()
                if news_item.end_datetime
                else start_date
            )
            current_date = start_date

            while current_date <= end_date:
                date_key = current_date.strftime("%Y-%m-%d")
                calendar_events.setdefault(date_key, []).append({
                    "id": news_item.pk,
                    "title": news_item.title,
                    "desc": news_item.description or "",
                    "focus": "News update",
                    "category": "upcoming",
                    "icon": "📰",
                    "status": news_item.get_status_display(),
                    "start": timezone.localtime(occurrence_datetime).strftime("%I:%M %p"),
                    "end": (
                        timezone.localtime(news_item.end_datetime).strftime("%I:%M %p")
                        if news_item.end_datetime
                        else ""
                    ),
                    "url": f"/news_feed/view/{news_item.pk}/",
                })
                current_date += timedelta(days=1)

        # json_script serializes the value in the template, so pass the Python
        # object here; pre-encoding it would make the browser parse a string.
        context["calendar_events_json"] = calendar_events

        context["upcoming_event_count"] = sum(
            len(events)
            for events in calendar_events.values()
        )

        return context


class WorkflowConfigurationAccessMixin(LoginRequiredMixin, CanAccessOrganizationMixin):
    def get_workflow_configuration_company_queryset(self):
        queryset = Company.objects.filter(is_active=True).order_by("company_name")
        user = self.request.user
        if user.is_superuser or getattr(user, "is_super_admin", False):
            return queryset
        if getattr(user, "company_id", None):
            return queryset.filter(pk=user.company_id)
        return queryset.none()

    def get_workflow_configuration_template_queryset(self):
        queryset = (
            ApprovalConfigurationTemplate.objects.select_related("company")
            .prefetch_related("stages", "stages__role", "stages__escalation_role")
            .order_by("company__company_name", "framework", "name")
        )
        user = self.request.user
        if user.is_superuser or getattr(user, "is_super_admin", False):
            return queryset
        if getattr(user, "company_id", None):
            return queryset.filter(company_id=user.company_id)
        return queryset.none()

    def get_workflow_configuration_template(self, pk):
        return get_object_or_404(self.get_workflow_configuration_template_queryset(), pk=pk)

    def get_stage_payload(self, stage):
        return {
            "id": stage.id,
            "level": stage.level,
            "label": stage.label,
            "stage_type": stage.get_stage_type_display(),
            "role": stage.role.role_name if stage.role_id else "",
            "role_code": stage.role.role_code if stage.role_id else "",
            "can_approve": stage.can_approve,
            "can_reject": stage.can_reject,
            "can_reassign": stage.can_reassign,
            "can_escalate": stage.can_escalate,
            "due_days": stage.due_days,
            "escalation_role": stage.escalation_role.role_name if stage.escalation_role_id else "",
        }


class WorkflowConfigurationTemplateListView(WorkflowConfigurationAccessMixin, ListView):
    model = ApprovalConfigurationTemplate
    template_name = "organizations/workflow_configurations/workflow_configuration_template_list.html"
    context_object_name = "workflow_configuration_templates"
    paginate_by = 12

    def get_queryset(self):
        queryset = self.get_workflow_configuration_template_queryset()
        search = self.request.GET.get("search", "").strip()
        company_id = self.request.GET.get("company", "").strip()
        framework = self.request.GET.get("framework", "").strip()

        if company_id:
            queryset = queryset.filter(company_id=company_id)
        if framework:
            queryset = queryset.filter(framework=framework)
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search)
                | Q(company__company_name__icontains=search)
                | Q(framework__icontains=search)
            )
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["search_query"] = self.request.GET.get("search", "")
        context["selected_company"] = self.request.GET.get("company", "")
        context["selected_framework"] = self.request.GET.get("framework", "")
        context["companies"] = self.get_workflow_configuration_company_queryset()
        context["framework_choices"] = ApprovalConfigurationTemplate.FRAMEWORK_CHOICES
        return context


class WorkflowConfigurationTemplateEditorView(WorkflowConfigurationAccessMixin, View):
    template_name = "organizations/workflow_configurations/workflow_configuration_template_form.html"

    def _get_template(self, pk=None):
        if pk:
            return self.get_workflow_configuration_template(pk)
        return None

    def _build_form(self, request_data=None, instance=None):
        form = WorkflowConfigurationTemplateForm(request_data or None, instance=instance)
        form.fields["company"].queryset = self.get_workflow_configuration_company_queryset()
        if instance and instance.company_id:
            form.initial.setdefault("company", instance.company_id)
        elif getattr(self.request.user, "company_id", None) and not (
            self.request.user.is_superuser or getattr(self.request.user, "is_super_admin", False)
        ):
            form.initial.setdefault("company", self.request.user.company_id)
        return form

    def _build_formset(self, request_data=None, instance=None):
        prefix = "stages"
        if request_data is None:
            return WorkflowConfigurationStageFormSet(instance=instance, prefix=prefix)
        return WorkflowConfigurationStageFormSet(request_data, instance=instance, prefix=prefix)

    def _render(self, request, form, formset, template_obj=None):
        context = {
            "form": form,
            "formset": formset,
            "object": template_obj,
            "companies": self.get_workflow_configuration_company_queryset(),
            "framework_choices": ApprovalConfigurationTemplate.FRAMEWORK_CHOICES,
            "stage_types": ApprovalConfigurationStage.STAGE_TYPE_CHOICES,
        }
        return render(request, self.template_name, context)

    def get(self, request, pk=None):
        template_obj = self._get_template(pk)
        form = self._build_form(instance=template_obj)
        formset = self._build_formset(instance=template_obj)
        return self._render(request, form, formset, template_obj)

    def post(self, request, pk=None):
        template_obj = self._get_template(pk)
        form = self._build_form(request.POST, instance=template_obj)
        formset = self._build_formset(request.POST, instance=template_obj)

        if form.is_valid() and formset.is_valid():
            with transaction.atomic():
                template = form.save()
                existing_stage_ids = []
                for index, stage_form in enumerate(formset.forms, start=1):
                    if not hasattr(stage_form, "cleaned_data"):
                        continue
                    if stage_form.cleaned_data.get("DELETE"):
                        continue
                    if not stage_form.cleaned_data:
                        continue

                    stage = stage_form.save(commit=False)
                    stage.template = template
                    stage.level = index
                    stage.save()
                    existing_stage_ids.append(stage.pk)

                template.stages.exclude(pk__in=existing_stage_ids).delete()

            messages.success(
                request,
                f"Workflow configuration template '{template.name}' saved successfully.",
            )
            return redirect("organizations:workflow_configuration_template_list")

        return self._render(request, form, formset, template_obj)


class WorkflowConfigurationTemplateDeleteView(WorkflowConfigurationAccessMixin, View):
    def post(self, request, pk):
        template = self.get_workflow_configuration_template(pk)
        name = template.name
        template.delete()
        messages.success(request, f"Workflow configuration template '{name}' deleted successfully.")
        return redirect("organizations:workflow_configuration_template_list")


class WorkflowConfigurationTaskHistoryView(WorkflowConfigurationAccessMixin, View):
    def get(self, request, pk):
        task = get_object_or_404(
            ApprovalConfigurationTask.objects.select_related("template", "current_stage"),
            pk=pk,
        )
        if not (
            request.user.is_superuser
            or getattr(request.user, "is_super_admin", False)
            or (request.user.company_id and task.template.company_id == request.user.company_id)
        ):
            return JsonResponse({"detail": "Not allowed."}, status=403)

        history = []
        for log in task.logs.select_related("from_stage", "to_stage", "actor_content_type").order_by("created_at"):
            history.append(
                {
                    "id": log.id,
                    "action": log.action,
                    "from_stage": log.from_stage.label if log.from_stage_id else "",
                    "to_stage": log.to_stage.label if log.to_stage_id else "",
                    "actor": str(log.actor) if log.actor else "",
                    "remark": log.remark or "",
                    "created_at": log.created_at.isoformat(),
                }
            )
        return JsonResponse({"task_id": task.id, "history": history})


# Backward-compatible aliases for any remaining imports or references.
ApprovalConfigurationAccessMixin = WorkflowConfigurationAccessMixin
ApprovalConfigurationTemplateListView = WorkflowConfigurationTemplateListView
ApprovalConfigurationTemplateEditorView = WorkflowConfigurationTemplateEditorView
ApprovalConfigurationTemplateDeleteView = WorkflowConfigurationTemplateDeleteView
ApprovalConfigurationTaskHistoryView = WorkflowConfigurationTaskHistoryView
