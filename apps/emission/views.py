# apps/emission/views.py - Updated views with company name passing

from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView
from django.http import JsonResponse, HttpResponse
from django.views import View
from django.urls import reverse_lazy
from dataclasses import dataclass
from typing import List, Dict, Any
from datetime import datetime
from rest_framework.views import APIView
from django.db import transaction
import json
from django.views.generic import (ListView,CreateView,UpdateView,DeleteView,)

from apps.organizations.services import financial_year
from .models import EmissionTransaction
from .forms import EmissionTransactionForm
from .models import *
from django.shortcuts import get_object_or_404
from apps.notifications.services import NotificationService
from apps.notifications.models import Notification,Timesheet
from apps.organizations.models import ApprovalConfigurationTemplate
from apps.organizations.workflow_configuration_engine import WorkflowConfigurationEngine
from django.utils import timezone
from apps.accounts.models import User
from decimal import Decimal
from django.db.models import Sum, Q, Count

# Notication and Timesheet 
from apps.common_events.event_context import EventContext
from apps.common_events.constants import *
from apps.common_events.services import EventService
from apps.goals.models import KPI
from apps.goals.services.notification import GoalNotificationService

import logging
logger = logging.getLogger(__name__)

def _approved_emission_transactions_queryset():
    """
    Return emission transactions that are allowed to appear
    in dashboards/reports.

    Unassigned transactions are visible.
    Assignment-linked transactions are visible only after
    the assignment is APPROVED.
    """
    return EmissionTransaction.objects.filter(
        Q(assignment__isnull=True) |
        Q(assignment__status="APPROVED")
    )



# apps/emission/views.py - Updated EmissionsDashboardView

class EmissionsDashboardView(TemplateView):
    """
    Renders the main Carbon Emissions Dashboard page
    (KPI cards, monthly trend, scope breakdown, by-plant chart,
    task status).
    """
    template_name = "emission/dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        from django.db.models import Sum, Q
        from .models import EmissionTransaction, EmissionScope, EmissionCategory, EmissionAssignment
        from apps.organizations.models import FinancialYear, Plant as PlantModel, FinancialMonth
        from decimal import Decimal
        from apps.notifications.models import Notification
        from apps.accounts.models import User
        
        # Get plant filter from request
        plant_id = self.request.GET.get('plant_id')
        selected_plant = None
        filter_kwargs = {}
        
        if plant_id:
            filter_kwargs['plant_id'] = plant_id
            try:
                selected_plant = PlantModel.objects.get(id=plant_id)
                context['selected_plant'] = selected_plant
            except:
                pass
        
        # Get plants for filter
        user = self.request.user
        if user.role.role_code in ['COMPANYADMIN', 'ESG-HEAD']:
            all_plants = PlantModel.objects.filter(is_active=True).order_by('name')
            context['plants'] = all_plants
        else:
            all_plants = user.assigned_plants.filter(is_active=True).order_by('name')
            context['plants'] = all_plants
        
        # Get current financial year
        today = timezone.now().date()
        current_fy = FinancialYear.objects.filter(
            start_date__lte=today,
            end_date__gte=today
        ).first()
        
        if current_fy:
            filter_kwargs['financial_year_id'] = current_fy.id
            context['current_fy'] = current_fy.name if hasattr(current_fy, 'name') else str(current_fy)
        else:
            context['current_fy'] = '2024–25'
        
        # ===== CALCULATE TOTALS =====
        # Total emissions in kg then convert to t
        total_emissions_kg = _approved_emission_transactions_queryset().filter(**filter_kwargs).aggregate(
            total=Sum('total_emission')
        )['total'] or Decimal('0')
        total_emissions_kg = Decimal(str(total_emissions_kg))
        total_emissions_t = float(total_emissions_kg / Decimal('1000'))
        
        # Scope totals
        scope_totals_t = {}
        for scope in EmissionScope.objects.filter(is_active=True):
            total_kg = _approved_emission_transactions_queryset().filter(
                **filter_kwargs,
                activity__category__scope_id=scope.id
            ).aggregate(total=Sum('total_emission'))['total'] or Decimal('0')
            total_kg = Decimal(str(total_kg))
            scope_totals_t[scope.code] = float(total_kg / Decimal('1000'))
        
        # Get scope totals for display
        scope1_total = scope_totals_t.get('S1', 0)
        scope2_total = scope_totals_t.get('S2', 0)
        scope3_total = scope_totals_t.get('S3', 0)
        total_emissions = total_emissions_t
        
        # Calculate deltas (compare with previous year)
        prev_fy = FinancialYear.objects.filter(
            end_date__lt=current_fy.start_date if current_fy else today
        ).order_by('-end_date').first()
        
        delta_scope1 = 0
        delta_scope2 = 0
        delta_scope3 = 0
        delta_total = 0
        
        if prev_fy:
            prev_filter = filter_kwargs.copy()
            prev_filter['financial_year_id'] = prev_fy.id
            
            prev_total_kg = _approved_emission_transactions_queryset().filter(**prev_filter).aggregate(
                total=Sum('total_emission')
            )['total'] or Decimal('0')
            prev_total_t = float(Decimal(str(prev_total_kg)) / Decimal('1000'))
            
            if prev_total_t > 0:
                delta_total = ((total_emissions - prev_total_t) / prev_total_t) * 100
            
            # Scope deltas
            for scope in EmissionScope.objects.filter(is_active=True):
                prev_kg = _approved_emission_transactions_queryset().filter(
                    **prev_filter,
                    activity__category__scope_id=scope.id
                ).aggregate(total=Sum('total_emission'))['total'] or Decimal('0')
                prev_t = float(Decimal(str(prev_kg)) / Decimal('1000'))
                
                if prev_t > 0:
                    delta = ((scope_totals_t.get(scope.code, 0) - prev_t) / prev_t) * 100
                    if scope.code == 'S1':
                        delta_scope1 = delta
                    elif scope.code == 'S2':
                        delta_scope2 = delta
                    elif scope.code == 'S3':
                        delta_scope3 = delta
        
        # Build KPI data
        context["kpis"] = [
            {
                "label": "TOTAL EMISSIONS YTD",
                "value": f"{total_emissions:,.2f}",
                "unit": "tCO₂e",
                "delta": f"{delta_total:.1f}",
                "accent": "green" if delta_total < 0 else "red"
            },
            {
                "label": "SCOPE 1 DIRECT",
                "value": f"{scope1_total:,.2f}",
                "unit": "tCO₂e",
                "delta": f"{delta_scope1:.1f}",
                "accent": "teal" if delta_scope1 < 0 else "orange"
            },
            {
                "label": "SCOPE 2 INDIRECT",
                "value": f"{scope2_total:,.2f}",
                "unit": "tCO₂e",
                "delta": f"{delta_scope2:.1f}",
                "accent": "blue" if delta_scope2 < 0 else "orange"
            },
            {
                "label": "SCOPE 3 VALUE CHAIN",
                "value": f"{scope3_total:,.2f}",
                "unit": "tCO₂e",
                "delta": f"{delta_scope3:.1f}",
                "accent": "orange" if delta_scope3 < 0 else "orange"
            },
        ]
        
        # ===== MONTHLY TREND DATA =====
        months = []
        scope1_series = []
        scope2_series = []
        scope3_series = []
        
        # Get last 12 months of data
        last_12_months = FinancialMonth.objects.filter(
            is_active=True
        ).order_by('-display_order')[:12]
        
        if last_12_months.exists():
            for month in reversed(last_12_months):
                month_filter = filter_kwargs.copy()
                month_filter['financial_month_id'] = month.id
                
                s1_kg = _approved_emission_transactions_queryset().filter(
                    **month_filter,activity__category__scope__code='S1'
                ).aggregate(total=Sum('total_emission'))['total'] or Decimal('0')
                s1 = float(Decimal(str(s1_kg)) / Decimal('1000'))

                s2_kg = _approved_emission_transactions_queryset().filter(
                    **month_filter,activity__category__scope__code='S2'
                ).aggregate(total=Sum('total_emission'))['total'] or Decimal('0')
                s2 = float(Decimal(str(s2_kg)) / Decimal('1000'))
                
                s3_kg = _approved_emission_transactions_queryset().filter(
                    **month_filter,activity__category__scope__code='S3'
                ).aggregate(total=Sum('total_emission'))['total'] or Decimal('0')
                s3 = float(Decimal(str(s3_kg)) / Decimal('1000'))
                
                months.append(month.name[:3] if hasattr(month, 'name') else str(month.month_number))
                scope1_series.append(s1)
                scope2_series.append(s2)
                scope3_series.append(s3)
        else:
            # Fallback to default data
            months = ["Apr", "May", "Jun", "Jul", "Aug", "Sep",
                      "Oct", "Nov", "Dec", "Jan", "Feb", "Mar"]
            scope1_series = [1420, 1390, 1350, 1300, 1480, 1550, 1500, 1380, 1300, 1250, 1300, 1400]
            scope2_series = [980, 950, 900, 870, 1000, 1050, 1000, 910, 860, 830, 870, 930]
            scope3_series = [2450, 2380, 2300, 2250, 2500, 2600, 2550, 2300, 2200, 2150, 2250, 2400]
        
        context["months"] = months
        context["scope1_series"] = scope1_series
        context["scope2_series"] = scope2_series
        context["scope3_series"] = scope3_series
        
        # ===== SCOPE BREAKDOWN FOR DONUT =====
        total = total_emissions if total_emissions > 0 else 1
        context["scope_breakdown"] = [
            {"name": "Scope 1", "value": scope1_total, "pct": (scope1_total / total) * 100, "color": "#22c07a"},
            {"name": "Scope 2", "value": scope2_total, "pct": (scope2_total / total) * 100, "color": "#17b6a7"},
            {"name": "Scope 3", "value": scope3_total, "pct": (scope3_total / total) * 100, "color": "#3b6df0"},
        ]
        
        # ===== BY PLANT DATA - NOW INCLUDES ALL PLANTS =====
        plants_data = []
        plant_filter = filter_kwargs.copy()
        if 'plant_id' in plant_filter:
            plant_filter.pop('plant_id', None)
        
        # Get total sources count for completion calculation
        total_sources_count = EmissionSource.objects.filter(is_active=True).count() or 1
        
        # Loop through ALL plants
        for plant in all_plants:
            p_filter = plant_filter.copy()
            p_filter['plant_id'] = plant.id
            if current_fy:
                p_filter['financial_year_id'] = current_fy.id
            
            total_kg = _approved_emission_transactions_queryset().filter(**p_filter).aggregate(
                total=Sum('total_emission')
            )['total'] or Decimal('0')
            total_t = float(Decimal(str(total_kg)) / Decimal('1000'))
            
            # Calculate completion percentage for this plant
            completed_sources = _approved_emission_transactions_queryset().filter(
                **p_filter
            ).values('source_id').distinct().count()
            
            completion_pct = (completed_sources / total_sources_count) * 100 if total_sources_count > 0 else 0
            
            plants_data.append({
                "id": plant.id,
                "name": plant.name,
                "value": total_t,
                "completion_pct": completion_pct,
                "completed_sources": completed_sources,
                "total_sources": total_sources_count,
            })
        
        # Sort by value descending (plants with data first)
        plants_data.sort(key=lambda x: (x['value'] == 0, -x['value']))
        
        # Pass ALL plants to the template
        context["by_plant"] = plants_data  # No limit - show all plants
        
        # Also pass all_plants for the filter dropdown
        context["all_plants"] = [{"id": p.id, "name": p.name} for p in all_plants]
        
        # ===== TASK STATUS - Using EmissionAssignment =====
        # Build filter for assignments
        assignment_filter = {}
        if plant_id:
            assignment_filter['plant_id'] = plant_id
        if current_fy:
            assignment_filter['financial_year_id'] = current_fy.id
        
        # Get all assignments for the company
        if user.company:
            assignment_filter['company_id'] = user.company.id
        
        # Total assignments
        total_assignments = EmissionAssignment.objects.filter(**assignment_filter).count()
        
        # Completed assignments (APPROVED or REVIEW_APPROVED status)
        completed_assignments = EmissionAssignment.objects.filter(
            **assignment_filter,
            status__in=['APPROVED', 'REVIEW_APPROVED']
        ).count()
        
        # Pending assignments (ASSIGNED, IN_PROGRESS, SUBMITTED)
        pending_assignments = EmissionAssignment.objects.filter(
            **assignment_filter,
            status__in=['ASSIGNED', 'IN_PROGRESS', 'SUBMITTED']
        ).count()
        
        # Overdue assignments (due date passed and not APPROVED or REVIEW_APPROVED)
        overdue_assignments = EmissionAssignment.objects.filter(
            **assignment_filter,
            due_date__lt=timezone.now().date()
        ).exclude(
            status__in=['APPROVED', 'REVIEW_APPROVED']
        ).count()
        
        context["task_status"] = {
            "total": total_assignments,
            "completed": completed_assignments,
            "pending_review": pending_assignments,
            "overdue": overdue_assignments,
        }
        
        return context

    def get(self, request, *args, **kwargs):
        # Check if PDF download is requested
        if request.GET.get('download_pdf'):
            from apps.emission.services.pdf_generator import generate_emission_pdf_report
            
            # Get user with company
            user = request.user
            company_name = None
            if user.is_authenticated:
                user = User.objects.select_related('company').get(id=user.id)
                if user.company:
                    company_name = user.company.company_name
            
            company_id = request.GET.get('company_id')
            plant_id = request.GET.get('plant_id')
            year_id = request.GET.get('year_id')
            month_id = request.GET.get('month_id')
            
            pdf_buffer = generate_emission_pdf_report(
                company_id=company_id,
                plant_id=plant_id,
                financial_year_id=year_id,
                financial_month_id=month_id,
                company_name=company_name,
                user=user,
            )
            
            timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
            filename = f"emission_dashboard_report_{timestamp}.pdf"
            
            response = HttpResponse(pdf_buffer.getvalue(), content_type='application/pdf')
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            return response
        
        return super().get(request, *args, **kwargs)

class EmissionsDashboardDataView(View):
    """
    JSON endpoint for fetching dashboard data via AJAX
    """
    def get(self, request, *args, **kwargs):
        from decimal import Decimal
        from django.db.models import Sum
        from .models import EmissionTransaction, EmissionScope, EmissionAssignment, EmissionSource
        from apps.organizations.models import FinancialYear, Plant as PlantModel
        from apps.accounts.models import User
        
        # Get plant filter
        plant_id = request.GET.get('plant_id')
        filter_kwargs = {}
        
        if plant_id:
            filter_kwargs['plant_id'] = plant_id
        
        # Get current financial year
        today = timezone.now().date()
        current_fy = FinancialYear.objects.filter(
            start_date__lte=today,
            end_date__gte=today
        ).first()
        
        if current_fy:
            filter_kwargs['financial_year_id'] = current_fy.id
        
        # Calculate totals
        total_emissions_kg = _approved_emission_transactions_queryset().filter(**filter_kwargs).aggregate(
            total=Sum('total_emission')
        )['total'] or Decimal('0')
        total_emissions_t = float(Decimal(str(total_emissions_kg)) / Decimal('1000'))
        
        # Scope totals
        scope_totals_t = {}
        for scope in EmissionScope.objects.filter(is_active=True):
            total_kg = _approved_emission_transactions_queryset().filter(
                **filter_kwargs,
                activity__category__scope_id=scope.id
            ).aggregate(total=Sum('total_emission'))['total'] or Decimal('0')
            total_kg = Decimal(str(total_kg))
            scope_totals_t[scope.code] = float(total_kg / Decimal('1000'))
        
        # Get scope totals
        scope1_total = scope_totals_t.get('S1', 0)
        scope2_total = scope_totals_t.get('S2', 0)
        scope3_total = scope_totals_t.get('S3', 0)
        
        # Calculate percentages
        total = total_emissions_t if total_emissions_t > 0 else 1
        
        # ===== BY PLANT DATA WITH COMPLETION PERCENTAGE - ALL PLANTS =====
        plants_data = []
        plant_filter = filter_kwargs.copy()
        if 'plant_id' in plant_filter:
            plant_filter.pop('plant_id', None)
        
        # Get all active sources count for completion calculation
        total_all_sources = EmissionSource.objects.filter(is_active=True).count() or 1
        
        # Get ALL plants (including those with no data)
        user = request.user
        if user.role.role_code in ['COMPANYADMIN', 'ESG-HEAD']:
            all_plants = PlantModel.objects.filter(is_active=True).order_by('name')
        else:
            all_plants = user.assigned_plants.filter(is_active=True).order_by('name')
        
        for plant in all_plants:
            p_filter = plant_filter.copy()
            p_filter['plant_id'] = plant.id
            if current_fy:
                p_filter['financial_year_id'] = current_fy.id
            
            total_kg = _approved_emission_transactions_queryset().filter(**p_filter).aggregate(
                total=Sum('total_emission')
            )['total'] or Decimal('0')
            total_t = float(Decimal(str(total_kg)) / Decimal('1000'))
            
            # Calculate completion percentage for this plant
            completed_sources = _approved_emission_transactions_queryset().filter(
                **p_filter
            ).values('source_id').distinct().count()
            
            completion_pct = (completed_sources / total_all_sources) * 100 if total_all_sources > 0 else 0
            
            plants_data.append({
                "id": plant.id,
                "name": plant.name,
                "value": total_t,
                "completion_pct": completion_pct,
                "completed_sources": completed_sources,
                "total_sources": total_all_sources,
            })
        
        # Sort: plants with data first, then alphabetically
        plants_data.sort(key=lambda x: (x['value'] == 0, -x['value']))
        
        # ===== TASK STATUS =====
        user = request.user
        assignment_filter = {}
        if plant_id:
            assignment_filter['plant_id'] = plant_id
        if current_fy:
            assignment_filter['financial_year_id'] = current_fy.id
        if user.company:
            assignment_filter['company_id'] = user.company.id
        
        total_assignments = EmissionAssignment.objects.filter(**assignment_filter).count()
        completed_assignments = EmissionAssignment.objects.filter(
            **assignment_filter,
            status__in=['APPROVED', 'REVIEW_APPROVED']
        ).count()
        pending_assignments = EmissionAssignment.objects.filter(
            **assignment_filter,
            status__in=['ASSIGNED', 'IN_PROGRESS', 'SUBMITTED']
        ).count()
        overdue_assignments = EmissionAssignment.objects.filter(
            **assignment_filter,
            due_date__lt=timezone.now().date()
        ).exclude(
            status__in=['APPROVED', 'REVIEW_APPROVED']
        ).count()
        
        data = {
            "kpis": {
                "total_ytd": total_emissions_t,
                "scope1": scope1_total,
                "scope2": scope2_total,
                "scope3": scope3_total,
            },
            "scope_breakdown": [
                {"name": "Scope 1", "value": scope1_total, "pct": (scope1_total / total) * 100, "color": "#22c07a"},
                {"name": "Scope 2", "value": scope2_total, "pct": (scope2_total / total) * 100, "color": "#17b6a7"},
                {"name": "Scope 3", "value": scope3_total, "pct": (scope3_total / total) * 100, "color": "#3b6df0"},
            ],
            "by_plant": plants_data,  # Send ALL plants
            "task_status": {
                "total": total_assignments,
                "completed": completed_assignments,
                "pending_review": pending_assignments,
                "overdue": overdue_assignments,
            },
        }
        return JsonResponse(data)

from django.views.generic import TemplateView
from django.db.models import Q
from django.utils import timezone

from .models import EmissionAssignment


# views.py

class EmissionAssignmentDashboardView(LoginRequiredMixin, TemplateView):
    login_url = "accounts:login"
    template_name = "emission/assignment.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get the user from the request
        user = self.request.user
        
        # Get assignment_id from URL parameters
        assignment_id = self.request.GET.get('assignment')
        
        # Get all assignments
        if user.role.role_code == "COMPANYADMIN":
            assignments = EmissionAssignment.objects.filter(company=user.company)

        elif user.role.role_code == "ESG-HEAD":
            assignments = EmissionAssignment.objects.filter(company=user.company)

        elif user.role.role_code == "ESG-COORD":
            assignments = EmissionAssignment.objects.filter(company=user.company,plant__in=user.assigned_plants.all()).distinct()

        elif user.role.role_code in ["DEPT-REVIEW", "PLANT-COORD"]:
            assignments = EmissionAssignment.objects.filter(company=user.company,reviewer=user)
        
        elif user.role.role_code == "DEPT-USER":
            assignments = EmissionAssignment.objects.filter(company=user.company,assignee=user)

        else:
            assignments = EmissionAssignment.objects.none()

        assignments = (
            assignments
            .select_related("company","plant","financial_year","financial_month","scope","assignee",
                            "assigner","reviewer",).prefetch_related("transactions","assignment_sources__source__activity",)
                            .order_by("-created_at"))

        # ==========================================
        # Plant Filter
        # ==========================================

        selected_plant = self.request.GET.get("plant")
        selected_scope = self.request.GET.get("scope")
        selected_source = self.request.GET.get("source")

        if selected_plant:
            assignments = assignments.filter(plant_id=selected_plant)

        if selected_scope:
            assignments = assignments.filter(scope_id=selected_scope)

        if selected_source:
            assignments = assignments.filter(assignment_sources__source_id=selected_source).distinct()
        
        # Validate assignment_id
        highlight_assignment_id = None
        if assignment_id:
            try:
                assignments.get(id=assignment_id)
                highlight_assignment_id = assignment_id
            except EmissionAssignment.DoesNotExist:
                pass
        
        # ====== GET ALL TIMESHEETS (including completed, overdue, rejected) ======
        timesheets = Timesheet.objects.filter(
            models.Q(user=user) | 
            models.Q(assignment__assignee=user)
        ).select_related('assignment', 'company', 'user').order_by('-created_at')[:10]
        
        # ====== COUNT ONLY UNREAD for the badge (assigned and viewed) ======
        timesheet_count = Timesheet.objects.filter(
            models.Q(user=user) | 
            models.Q(assignment__assignee=user)
        ).filter(
            models.Q(status='assigned') | models.Q(status='viewed')
        ).count()
        
        # ====== GET NOTIFICATIONS ======
        # Get ALL notifications (read and unread) for the dropdown
        navbar_notifications = Notification.objects.filter(
            recipient=user
        ).exclude(
            title__icontains='Timesheet'
        ).order_by('-created_at')[:10]
        
        # Count ONLY unread for the badge
        navbar_notification_count = Notification.objects.filter(
            recipient=user,
            is_read=False
        ).exclude(
            title__icontains='Timesheet'
        ).count()
        
        # ==========================================================
        # Dashboard Statistics & Filtering
        # ==========================================================

        today = timezone.now().date()

        # Keep original queryset for dashboard counts
        all_assignments = assignments

        # Dashboard cards counts (Always show total counts)
        assignment_stats = {
            "assignment_count": all_assignments.count(),
            "open_count": all_assignments.filter(
                status__in=["ASSIGNED", "IN_PROGRESS", "SUBMITTED"]
            ).count(),
            "completed_count": all_assignments.filter(
                status="APPROVED"
            ).count(),
            "overdue_count": all_assignments.filter(
                due_date__lt=today
            ).exclude(
                status="APPROVED"
            ).count(),
        }

        # ==========================================================
        # Apply Dashboard Filter
        # ==========================================================

        status_filter = self.request.GET.get("status", "open")

        if status_filter == "open":
            assignments = all_assignments.filter(
                status__in=["ASSIGNED", "IN_PROGRESS", "SUBMITTED"]
            )

        elif status_filter == "completed":
            assignments = all_assignments.filter(
                status="APPROVED"
            )

        elif status_filter == "overdue":
            assignments = all_assignments.filter(
                due_date__lt=today
            ).exclude(
                status="APPROVED"
            )

        else:
            assignments = all_assignments

        plants = Plant.objects.filter(id__in=all_assignments.values_list("plant_id",flat=True).distinct()).order_by("name")

        scopes = EmissionScope.objects.filter(id__in=all_assignments.values_list("scope_id",flat=True).distinct()).order_by("display_order")

        if selected_scope:
            sources = EmissionSource.objects.filter(
                activity__category__scope_id=selected_scope
            ).order_by("source_name")
        else:
            sources = EmissionSource.objects.filter(
                assignment_sources__assignment__in=all_assignments
            ).distinct().order_by("source_name")

        # ==========================================================
        # Update Context
        # ==========================================================

        context.update({
            "assignments": assignments,
            "assignment_scope": "ALL ASSIGNMENTS",
            "current_filter": status_filter,
            "highlight_assignment_id": highlight_assignment_id,
            "timesheets": timesheets,
            "timesheet_count": timesheet_count,
            "navbar_notifications": navbar_notifications,
            "navbar_notification_count": navbar_notification_count,
            **assignment_stats,
            "plants": plants,
            "selected_plant": selected_plant,
            "current_filter": status_filter,
            "scopes": scopes,
            "sources": sources,
            "selected_scope": selected_scope,
            "selected_source": selected_source,
        })

        return context


import traceback

from django.contrib.auth import get_user_model
from django.db import transaction

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .assignment_service import create_emission_assignment
from .models import EmissionAssignmentSource


User = get_user_model()
class SaveEmissionAssignmentAPIView(APIView):

    @transaction.atomic
    def post(self, request):

        data = request.data

        try:

            # -------------------------------------------------
            # Prevent duplicate source assignment
            # -------------------------------------------------

            source_ids = data.get("source_ids", [])

            existing_sources = (
                EmissionAssignmentSource.objects
                .filter(
                    assignment__company_id=data.get("company"),
                    assignment__plant_id=data.get("plant"),
                    assignment__financial_year_id=data.get("financial_year"),
                    assignment__financial_month_id=data.get("financial_month"),
                    assignment__assignee_id=data.get("assignee"),
                    source_id__in=source_ids,
                )
                .select_related("source")
            )

            if existing_sources.exists():

                assigned_sources = ", ".join(
                    existing_sources.values_list(
                        "source__source_name",
                        flat=True,
                    ).distinct()
                )

                return Response(
                    {
                        "success": False,
                        "message": (
                            "The selected user is already assigned to the "
                            f"following source(s): {assigned_sources}"
                        ),
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # -------------------------------------------------
            # Create Assignment
            # -------------------------------------------------

            assignment = create_emission_assignment(

                company_id=data.get("company"),

                plant_id=data.get("plant"),

                financial_year_id=data.get("financial_year"),

                financial_month_id=data.get("financial_month"),

                scope_id=data.get("scope_id"),

                assignee=User.objects.get(
                    id=data.get("assignee")
                ),

                assigner=request.user,

                reviewer=(
                    User.objects.get(id=data.get("reviewer"))
                    if data.get("reviewer")
                    else None
                ),

                due_date=data.get("due_date"),

                frequency=data.get("frequency"),

                priority=data.get("priority"),

                notes=data.get("notes"),

                source_ids=source_ids,

            )

            return Response(
                {
                    "success": True,
                    "message": "Assignment created successfully.",
                    "assignment_id": assignment.id,
                    "assignment_code": assignment.assignment_code,
                },
                status=status.HTTP_201_CREATED,
            )

        except Exception as e:

            traceback.print_exc()

            return Response(
                {
                    "success": False,
                    "message": str(e),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
# apps/emission/views.py - Complete updated ESGDisclosureView with category completion

class ESGDisclosureView(TemplateView):
    template_name = 'emission/report.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['current_year'] = datetime.now().year
        
        # Get plant filter
        plant_id = self.request.GET.get('plant_id')
        selected_plant = None
        
        # Build filter for transactions
        filter_kwargs = {}
        if plant_id:
            filter_kwargs['plant_id'] = plant_id
            from apps.organizations.models import Plant as PlantModel
            try:
                selected_plant = PlantModel.objects.get(id=plant_id)
                context['selected_plant'] = selected_plant
            except:
                pass
        
        # Get plants for filter
        user = self.request.user
        from apps.organizations.models import Plant as PlantModel
        
        if user.role.role_code in ['COMPANYADMIN', 'ESG-HEAD']:
            context['plants'] = PlantModel.objects.filter(is_active=True).order_by('name')
        else:
            context['plants'] = user.assigned_plants.filter(is_active=True).order_by('name')
        
        # Get emissions data
        from django.db.models import Sum, Q, Count
        from .models import EmissionTransaction, EmissionScope, EmissionCategory, EmissionSource, EmissionActivity
        from apps.organizations.models import FinancialYear
        
        # Get current financial year (or use default if none selected)
        today = timezone.now().date()
        current_fy = FinancialYear.objects.filter(
            start_date__lte=today,
            end_date__gte=today
        ).first()
        
        if current_fy:
            filter_kwargs['financial_year_id'] = current_fy.id
        
        # ===== CALCULATE TOTALS IN tCO₂e =====
        total_emissions_kg =  _approved_emission_transactions_queryset().filter(**filter_kwargs).aggregate(
            total=Sum('total_emission')
        )['total'] or Decimal('0')
        total_emissions_kg = Decimal(str(total_emissions_kg))
        total_emissions_t = total_emissions_kg / Decimal('1000')
        
        # Get scope totals
        scope_totals_t = {}
        for scope in EmissionScope.objects.filter(is_active=True):
            total_kg = _approved_emission_transactions_queryset().filter(
                **filter_kwargs,
                activity__category__scope_id=scope.id
            ).aggregate(total=Sum('total_emission'))['total'] or Decimal('0')
            total_kg = Decimal(str(total_kg))
            scope_totals_t[scope.code] = total_kg / Decimal('1000')
        
        context['total_emissions'] = total_emissions_t
        context['scope1_total'] = scope_totals_t.get('S1', Decimal('0'))
        context['scope2_total'] = scope_totals_t.get('S2', Decimal('0'))
        context['scope3_total'] = scope_totals_t.get('S3', Decimal('0'))
        
        # Calculate percentages
        if total_emissions_t > 0:
            context['scope1_percentage'] = (context['scope1_total'] / total_emissions_t) * Decimal('100')
            context['scope2_percentage'] = (context['scope2_total'] / total_emissions_t) * Decimal('100')
            context['scope3_percentage'] = (context['scope3_total'] / total_emissions_t) * Decimal('100')
        else:
            context['scope1_percentage'] = Decimal('0')
            context['scope2_percentage'] = Decimal('0')
            context['scope3_percentage'] = Decimal('0')
        
        # ===== CALCULATE CATEGORY COMPLETION PERCENTAGES =====
        scope_breakdown = []
        scopes = EmissionScope.objects.filter(is_active=True).order_by('display_order')
        
        for scope in scopes:
            scope_total_t = scope_totals_t.get(scope.code, Decimal('0'))
            scope_data = {
                'code': scope.code,
                'name': scope.name,
                'total': scope_total_t,
                'categories': []
            }
            
            # Get categories for this scope
            categories = EmissionCategory.objects.filter(
                scope=scope,
                is_active=True
            ).order_by('display_order')
            
            for category in categories:
                # Get all sources for this category
                sources = EmissionSource.objects.filter(
                    activity__category=category,
                    is_active=True
                )
                total_sources = sources.count()
                
                # Get completed/transacted sources count (sources that have transactions)
                completed_sources = _approved_emission_transactions_queryset().filter(
                    **filter_kwargs,
                    activity__category_id=category.id
                ).values('source_id').distinct().count()
                
                # Calculate completion percentage
                if total_sources > 0:
                    completion_pct = (completed_sources / total_sources) * 100
                else:
                    completion_pct = 0
                
                # Get total emission for this category
                cat_total_kg = _approved_emission_transactions_queryset().filter(
                    **filter_kwargs,
                    activity__category_id=category.id
                ).aggregate(total=Sum('total_emission'))['total'] or Decimal('0')
                cat_total_kg = Decimal(str(cat_total_kg))
                cat_total_t = cat_total_kg / Decimal('1000')
                
                # Calculate percentage of total scope
                if scope_total_t > 0:
                    pct_of_scope = (cat_total_t / scope_total_t) * Decimal('100')
                else:
                    pct_of_scope = Decimal('0')
                
                scope_data['categories'].append({
                    'name': category.name,
                    'total': float(cat_total_t),  # Emission value in tCO₂e
                    'percentage': float(pct_of_scope),  # Percentage of scope total
                    'completion_pct': float(completion_pct),  # Completion percentage
                    'completed_sources': completed_sources,
                    'total_sources': total_sources,
                })
            
            if scope_total_t > 0 or scope_data['categories']:
                scope_breakdown.append(scope_data)
        
        context['scope_breakdown'] = scope_breakdown
        
        # ===== CHART DATA - Dynamic based on available financial years =====
        from apps.organizations.models import FinancialYear
        
        # Get distinct financial years that have transactions
        transaction_fy_ids = _approved_emission_transactions_queryset().filter(
            **filter_kwargs
        ).values_list('financial_year_id', flat=True).distinct()
        
        # Get the actual FinancialYear objects
        financial_years_with_data = FinancialYear.objects.filter(
            id__in=transaction_fy_ids
        ).order_by('start_date')
        
        # If we have financial years with data, use them
        if financial_years_with_data.exists():
            years = []
            scope1_data = []
            scope2_data = []
            scope3_data = []
            intensity_data = []
            
            for fy in financial_years_with_data:
                fy_filter = filter_kwargs.copy()
                fy_filter['financial_year_id'] = fy.id
                
                # Get data in kg then convert to t
                s1_kg = _approved_emission_transactions_queryset().filter(
                    **fy_filter,
                    activity__category__scope__code='S1'
                ).aggregate(total=Sum('total_emission'))['total'] or Decimal('0')
                s1_kg = Decimal(str(s1_kg))
                s1_t = s1_kg / Decimal('1000')
                
                s2_kg = _approved_emission_transactions_queryset().filter(
                    **fy_filter,
                    activity__category__scope__code='S2'
                ).aggregate(total=Sum('total_emission'))['total'] or Decimal('0')
                s2_kg = Decimal(str(s2_kg))
                s2_t = s2_kg / Decimal('1000')
                
                s3_kg = _approved_emission_transactions_queryset().filter(
                    **fy_filter,
                    activity__category__scope__code='S3'
                ).aggregate(total=Sum('total_emission'))['total'] or Decimal('0')
                s3_kg = Decimal(str(s3_kg))
                s3_t = s3_kg / Decimal('1000')
                
                scope1_data.append(float(s1_t))
                scope2_data.append(float(s2_t))
                scope3_data.append(float(s3_t))
                
                # Calculate intensity
                total_t = s1_t + s2_t + s3_t
                fy_transaction_count = _approved_emission_transactions_queryset().filter(**fy_filter).count() or 1
                intensity = total_t / Decimal(str(fy_transaction_count)) if fy_transaction_count > 0 else Decimal('0')
                intensity_data.append(float(intensity))
                
                # Get year label
                if hasattr(fy, 'name'):
                    years.append(str(fy.name))
                elif hasattr(fy, 'start_date'):
                    years.append(f"FY{fy.start_date.year}")
                else:
                    years.append(str(fy.id))
            
            chart_data = {
                'years': years,
                'scope1': scope1_data,
                'scope2': scope2_data,
                'scope3': scope3_data,
                'intensity': intensity_data
            }
        else:
            # No data found - use empty arrays
            chart_data = {
                'years': [],
                'scope1': [],
                'scope2': [],
                'scope3': [],
                'intensity': []
            }
        
        context['chart_data'] = chart_data
        
        # Get individual chart data for easier template access
        context['scope1_chart_data'] = chart_data['scope1']
        context['scope2_chart_data'] = chart_data['scope2']
        context['scope3_chart_data'] = chart_data['scope3']
        context['intensity_chart_data'] = chart_data['intensity']
        context['chart_years'] = chart_data['years']
        
        # Check if we have chart data
        context['has_chart_data'] = len(chart_data['years']) > 0
        
        # Calculate GHG Intensity
        transaction_count = _approved_emission_transactions_queryset().filter(**filter_kwargs).count() or 1
        ghg_intensity = total_emissions_t / Decimal(str(transaction_count)) if transaction_count > 0 else Decimal('0')
        context['ghg_intensity'] = ghg_intensity
        context['intensity_change'] = Decimal('-10.3')
        context['intensity_reduction'] = Decimal('23.2')
        
        # Get financial year display name safely
        if current_fy:
            if hasattr(current_fy, 'name'):
                context['current_fy'] = current_fy.name
            elif hasattr(current_fy, 'start_date'):
                context['current_fy'] = f"FY{current_fy.start_date.year}-{current_fy.end_date.year}"
            else:
                context['current_fy'] = str(current_fy.id)
        else:
            context['current_fy'] = '2024–25'
        
        return context
    
    def get(self, request, *args, **kwargs):
        # Check if PDF download is requested
        if request.GET.get('download_pdf'):
            from apps.emission.service.pdf_generator import generate_emission_pdf_report
            from django.http import HttpResponse
            from django.utils import timezone
            from apps.accounts.models import User
            
            # Get user with company
            user = request.user
            company_name = None
            if user.is_authenticated:
                user = User.objects.select_related('company').get(id=user.id)
                if user.company:
                    company_name = user.company.company_name
                    print(f"DEBUG: Company name from user: {company_name}")
                else:
                    print(f"DEBUG: User has no company assigned!")
            
            # Get filter parameters
            plant_id = request.GET.get('plant_id')
            company_id = request.GET.get('company_id')
            year_id = request.GET.get('year_id')
            month_id = request.GET.get('month_id')
            
            # Generate PDF with company name
            pdf_buffer = generate_emission_pdf_report(
                company_id=company_id,
                plant_id=plant_id,
                financial_year_id=year_id,
                financial_month_id=month_id,
                company_name=company_name,
                user=user,
            )
            
            # Get plant name for filename
            plant_name = "all_plants"
            if plant_id:
                from apps.organizations.models import Plant as PlantModel
                try:
                    plant = PlantModel.objects.get(id=plant_id)
                    plant_name = plant.name.replace(' ', '_').lower()
                except:
                    pass
            
            timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
            filename = f"ESG_Report_{plant_name}_{timestamp}.pdf"
            
            response = HttpResponse(pdf_buffer.getvalue(), content_type='application/pdf')
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            return response
        
        return super().get(request, *args, **kwargs)
# apps/emission/views.py - Updated ESGDisclosureDataAPIView

class ESGDisclosureDataAPIView(View):
    """
    API endpoint to fetch ESG data for AJAX requests
    """
    def get(self, request):
        try:
            from decimal import Decimal
            from django.db.models import Sum, Count
            
            # Get plant filter
            plant_id = request.GET.get('plant_id')
            
            # Build filter for transactions
            filter_kwargs = {}
            if plant_id:
                filter_kwargs['plant_id'] = plant_id
            
            # Get current financial year
            from apps.organizations.models import FinancialYear
            today = timezone.now().date()
            current_fy = FinancialYear.objects.filter(
                start_date__lte=today,
                end_date__gte=today
            ).first()
            
            if current_fy:
                filter_kwargs['financial_year_id'] = current_fy.id
            
            # Calculate totals in kg then convert to t
            total_emissions_kg = _approved_emission_transactions_queryset().filter(**filter_kwargs).aggregate(
                total=Sum('total_emission')
            )['total'] or Decimal('0')
            total_emissions_kg = Decimal(str(total_emissions_kg))
            total_emissions_t = total_emissions_kg / Decimal('1000')
            
            # Get scope totals (convert to t)
            scope_totals_t = {}
            for scope in EmissionScope.objects.filter(is_active=True):
                total_kg = _approved_emission_transactions_queryset().filter(
                    **filter_kwargs,
                    activity__category__scope_id=scope.id
                ).aggregate(total=Sum('total_emission'))['total'] or Decimal('0')
                total_kg = Decimal(str(total_kg))
                scope_totals_t[scope.code] = total_kg / Decimal('1000')
            
            # Calculate percentages
            if total_emissions_t > 0:
                scope1_pct = (scope_totals_t.get('S1', Decimal('0')) / total_emissions_t) * Decimal('100')
                scope2_pct = (scope_totals_t.get('S2', Decimal('0')) / total_emissions_t) * Decimal('100')
                scope3_pct = (scope_totals_t.get('S3', Decimal('0')) / total_emissions_t) * Decimal('100')
            else:
                scope1_pct = scope2_pct = scope3_pct = Decimal('0')
            
            # Get scope breakdown with categories and completion percentages
            scope_breakdown = []
            scopes = EmissionScope.objects.filter(is_active=True).order_by('display_order')
            
            for scope in scopes:
                scope_total_t = scope_totals_t.get(scope.code, Decimal('0'))
                scope_data = {
                    'code': scope.code,
                    'name': scope.name,
                    'total': float(scope_total_t),
                    'categories': []
                }
                
                categories = EmissionCategory.objects.filter(
                    scope=scope,
                    is_active=True
                ).order_by('display_order')
                
                for category in categories:
                    # Get all sources for this category
                    sources = EmissionSource.objects.filter(
                        activity__category=category,
                        is_active=True
                    )
                    total_sources = sources.count()
                    
                    # Get completed sources
                    completed_sources = _approved_emission_transactions_queryset().filter(
                        **filter_kwargs,
                        activity__category_id=category.id
                    ).values('source_id').distinct().count()
                    
                    # Calculate completion percentage
                    if total_sources > 0:
                        completion_pct = (completed_sources / total_sources) * 100
                    else:
                        completion_pct = 0
                    
                    # Get category total
                    cat_total_kg = _approved_emission_transactions_queryset().filter(
                        **filter_kwargs,
                        activity__category_id=category.id
                    ).aggregate(total=Sum('total_emission'))['total'] or Decimal('0')
                    cat_total_kg = Decimal(str(cat_total_kg))
                    cat_total_t = cat_total_kg / Decimal('1000')
                    
                    if cat_total_t > 0 or scope_total_t > 0:
                        if scope_total_t > 0:
                            pct_of_scope = float((cat_total_t / scope_total_t) * Decimal('100'))
                        else:
                            pct_of_scope = 0
                        
                        scope_data['categories'].append({
                            'name': category.name,
                            'total': float(cat_total_t),
                            'percentage': pct_of_scope,
                            'completion_pct': float(completion_pct),
                            'completed_sources': completed_sources,
                            'total_sources': total_sources,
                        })
                
                if scope_total_t > 0 or scope_data['categories']:
                    scope_breakdown.append(scope_data)
            
            # ===== CHART DATA =====
            from apps.organizations.models import FinancialYear
            
            transaction_fy_ids = _approved_emission_transactions_queryset().filter(
                **filter_kwargs
            ).values_list('financial_year_id', flat=True).distinct()
            
            financial_years_with_data = FinancialYear.objects.filter(
                id__in=transaction_fy_ids
            ).order_by('start_date')
            
            chart_years = []
            scope1_chart_data = []
            scope2_chart_data = []
            scope3_chart_data = []
            intensity_chart_data = []
            
            if financial_years_with_data.exists():
                for fy in financial_years_with_data:
                    fy_filter = filter_kwargs.copy()
                    fy_filter['financial_year_id'] = fy.id
                    
                    s1_kg = _approved_emission_transactions_queryset().filter(
                        **fy_filter,
                        activity__category__scope__code='S1'
                    ).aggregate(total=Sum('total_emission'))['total'] or Decimal('0')
                    s1_kg = Decimal(str(s1_kg))
                    s1_t = s1_kg / Decimal('1000')
                    
                    s2_kg = _approved_emission_transactions_queryset().filter(
                        **fy_filter,
                        activity__category__scope__code='S2'
                    ).aggregate(total=Sum('total_emission'))['total'] or Decimal('0')
                    s2_kg = Decimal(str(s2_kg))
                    s2_t = s2_kg / Decimal('1000')
                    
                    s3_kg = _approved_emission_transactions_queryset().filter(
                        **fy_filter,
                        activity__category__scope__code='S3'
                    ).aggregate(total=Sum('total_emission'))['total'] or Decimal('0')
                    s3_kg = Decimal(str(s3_kg))
                    s3_t = s3_kg / Decimal('1000')
                    
                    scope1_chart_data.append(float(s1_t))
                    scope2_chart_data.append(float(s2_t))
                    scope3_chart_data.append(float(s3_t))
                    
                    total_t = s1_t + s2_t + s3_t
                    fy_transaction_count = _approved_emission_transactions_queryset().filter(**fy_filter).count() or 1
                    intensity = total_t / Decimal(str(fy_transaction_count)) if fy_transaction_count > 0 else Decimal('0')
                    intensity_chart_data.append(float(intensity))
                    
                    if hasattr(fy, 'name'):
                        chart_years.append(str(fy.name))
                    elif hasattr(fy, 'start_date'):
                        chart_years.append(f"FY{fy.start_date.year}")
                    else:
                        chart_years.append(str(fy.id))
            
            return JsonResponse({
                'success': True,
                'total_emissions': float(total_emissions_t),
                'scope1_total': float(scope_totals_t.get('S1', Decimal('0'))),
                'scope2_total': float(scope_totals_t.get('S2', Decimal('0'))),
                'scope3_total': float(scope_totals_t.get('S3', Decimal('0'))),
                'scope1_percentage': float(scope1_pct),
                'scope2_percentage': float(scope2_pct),
                'scope3_percentage': float(scope3_pct),
                'scope_breakdown': scope_breakdown,
                'chart_years': chart_years,
                'scope1_chart_data': scope1_chart_data,
                'scope2_chart_data': scope2_chart_data,
                'scope3_chart_data': scope3_chart_data,
                'intensity_chart_data': intensity_chart_data,
                'has_chart_data': len(chart_years) > 0,
            })
        except Exception as e:
            import traceback
            traceback.print_exc()
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)


from .models import (
    EmissionTransaction,
    EmissionScope,
    EmissionCategory,
)

from apps.companies.models import Company
from apps.organizations.models import (
    Plant,
    FinancialYear,
    FinancialMonth,
)
from .models import EmissionAssignment
from django.utils import timezone
from ..organizations.models import FinancialYear, FinancialMonth
from django.core.exceptions import PermissionDenied

class ScopeDashboardView(ListView):

    model = EmissionTransaction

    template_name = "emission/scope_dataentry.html"

    context_object_name = "transactions"

    paginate_by = 20

    def get_queryset(self):
        queryset = EmissionTransaction.objects.all()
        assignment_id = self.request.GET.get("assignment")

        if assignment_id:
            queryset = queryset.filter(
                assignment_id=assignment_id,
                assignment__status="APPROVED",
            )

        return queryset

    def get_context_data(self, **kwargs):

        context = super().get_context_data(**kwargs)

        assignment_id = self.request.GET.get("assignment")

        assignment = None

        if assignment_id:

            assignment = (
                EmissionAssignment.objects
                .select_related(
                    "company",
                    "plant",
                    "financial_year",
                    "financial_month",
                    "scope",
                    "assigner",
                    "assignee",
                )
                .prefetch_related(
                    "assignment_sources__source",
                )
                .filter(id=assignment_id)
                .first()
            )

            if not assignment:
                raise PermissionDenied("Assignment not found.")

            # --------------------------------------------------
            # Access Control
            # --------------------------------------------------
            is_assignee = assignment.assignee == self.request.user
            is_assigner = assignment.assigner == self.request.user

            # Change this according to your Role model
            is_reviewer = (
                assignment is not None
                and assignment.reviewer == self.request.user
            )

            if not (is_assignee or is_assigner or is_reviewer):
                raise PermissionDenied("You are not authorized to access this assignment.")

        context["assignment"] = assignment

        context["is_review_mode"] = (
            assignment is not None
            and assignment.status == "SUBMITTED"
            and assignment.reviewer == self.request.user
        )

        context["is_coordinator_review"] = (
            assignment is not None
            and assignment.status == "REVIEW_APPROVED"
            and assignment.assigner == self.request.user
        )

        context["is_assignee"] = (
            assignment is not None
            and assignment.assignee == self.request.user
        )

        context["is_assigner"] = (
            assignment is not None
            and assignment.assigner == self.request.user
        )

        context["is_reviewer"] = (
            assignment is not None
            and assignment.reviewer == self.request.user
        )

        context["reviewer_name"] = (
            assignment.reviewer.get_full_name()
            if assignment and assignment.reviewer
            else ""
        )

        context["coordinator_name"] = (
            assignment.assigner.get_full_name()
            if assignment and assignment.assigner
            else ""
        )

        if assignment and assignment.assigner and not context["coordinator_name"]:
            context["coordinator_name"] = assignment.assigner.username

        if assignment and assignment.reviewer and not context["reviewer_name"]:
            context["reviewer_name"] = assignment.reviewer.username

        

        if assignment:
            scope = (
                EmissionScope.objects
                .prefetch_related("categories")
                .get(id=assignment.scope_id)
            )
        else:
            scope = (
                EmissionScope.objects
                .prefetch_related("categories")
                .get(code="S1")
            )

        context["scope"] = scope

        if assignment:

            category_ids = (assignment.assignment_sources.values_list("source__activity__category_id",flat=True).distinct())

            context["categories"] = (scope.categories.filter(id__in=category_ids,is_active=True,).order_by("display_order"))

        else:

            context["categories"] = (
                scope.categories
                .filter(is_active=True)
                .order_by("display_order")
            )

        context["companies"] = Company.objects.filter(
            is_active=True
        ).order_by(
            "company_name"
        )

        user = self.request.user

        if user.role.role_code in ["COMPANYADMIN", "ESG-HEAD"]:
            # Can access all company plants
            context["plants"] = (
                Plant.objects.filter(
                    is_active=True,
                ).order_by("name")
            )

        else:
            # Only assigned plants
            context["plants"] = (
                user.assigned_plants.filter(
                    is_active=True,
                ).order_by("name")
            )

        context["can_view_all_plants"] = (
            self.request.user.role.role_code in [
                "COMPANYADMIN",
                "ESG-HEAD",
                "ESG-COORD",
            ]
        )
        context["can_assign"] = (
            assignment is None and
            self.request.user.role.role_code == "ESG-COORD"
        )

        context["financial_years"] = FinancialYear.objects.all()

        context["financial_months"] = (
            FinancialMonth.objects
            .filter(is_active=True)
            .order_by("display_order")
        )

        today = timezone.now().date()

        current_financial_year = (
            FinancialYear.objects.filter(
                start_date__lte=today,
                end_date__gte=today
            ).first()
        )

        current_month_number = today.month

        # Convert calendar month to your financial month numbering
        month_mapping = {
            4: 1,   # April
            5: 2,
            6: 3,
            7: 4,
            8: 5,
            9: 6,
            10: 7,
            11: 8,
            12: 9,
            1: 10,
            2: 11,
            3: 12,
        }

        current_financial_month = FinancialMonth.objects.filter(
            month_number=month_mapping[current_month_number]
        ).first()

        context["current_financial_year"] = current_financial_year
        context["current_financial_month"] = current_financial_month
        context["is_assignment_locked"] = (assignment is not None
            and assignment.status in ["SUBMITTED","REVIEW_APPROVED","APPROVED",])
        return context
    
    def get(self, request, *args, **kwargs):
        # Check if PDF download is requested
        if request.GET.get('download_pdf'):
            from apps.emission.services.pdf_generator import generate_emission_pdf_report
            from apps.accounts.models import User
            
            # Get user with company
            user = request.user
            company_name = None
            if user.is_authenticated:
                user = User.objects.select_related('company').get(id=user.id)
                if user.company:
                    company_name = user.company.company_name
                    print(f"DEBUG: Company name from user: {company_name}")
            
            assignment_id = request.GET.get('assignment')
            company_id = request.GET.get('company')
            plant_id = request.GET.get('plant')
            year_id = request.GET.get('financial_year')
            month_id = request.GET.get('financial_month')
            
            pdf_buffer = generate_emission_pdf_report(
                assignment_id=assignment_id,
                company_id=company_id,
                plant_id=plant_id,
                financial_year_id=year_id,
                financial_month_id=month_id,
                company_name=company_name,  # Pass company name
                user=user,  # Pass user object
            )
            
            timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
            filename = f"emission_data_{timestamp}.pdf"
            
            response = HttpResponse(pdf_buffer.getvalue(), content_type='application/pdf')
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            return response
        
        return super().get(request, *args, **kwargs)


from django.http import JsonResponse
from django.views import View

from .models import (
    EmissionActivity,
    EmissionSource,
)


class CategoryActivitiesView(View):

    def get(self, request, *args, **kwargs):

        category_id = request.GET.get("category_id")
        assignment_id = request.GET.get("assignment")

        assignment = None
        assigned_source_ids = []

        if assignment_id:

            assignment = (
                EmissionAssignment.objects
                .prefetch_related("assignment_sources")
                .filter(id=assignment_id)
                .first()
            )

            if assignment:

                is_assignee = assignment.assignee_id == request.user.id
                is_assigner = assignment.assigner_id == request.user.id
                is_reviewer = assignment.reviewer_id == request.user.id

                if not (is_assignee or is_assigner or is_reviewer):
                    return JsonResponse({"activities": []})

                assigned_source_ids = list(
                    assignment.assignment_sources.values_list(
                        "source_id",
                        flat=True,
                    )
                )

                print("Assigned Sources :", assigned_source_ids)

        activities = (
            EmissionActivity.objects.filter(
                category_id=category_id,
                is_active=True,
            )
            .select_related(
                "base_unit",
            )
            .prefetch_related(
                "sources",
            )
            .order_by(
                "display_order",
            )
        )

        data = []

        for activity in activities:

            sources = []

            if assignment_id:

                source_queryset = (
                    activity.sources.filter(
                        id__in=assigned_source_ids,
                        is_active=True,
                    ).order_by("display_order")
                )

            else:

                source_queryset = (
                    activity.sources.filter(
                        is_active=True,
                    ).order_by("display_order")
                )

            for source in source_queryset:

                sources.append(
                    {
                        "id": source.id,
                        "code": source.source_code,
                        "name": source.source_name,
                    }
                )
            if assignment and not sources:
                continue
            data.append(
                {
                    "id": activity.id,
                    "code": activity.code,
                    "name": activity.name,
                    "unit": activity.base_unit.symbol,
                    "base_unit_id": activity.base_unit.id,
                    "sources": sources,
                }
            )

        return JsonResponse(
            {
                "activities": data,
            }
        )
    




from django.utils import timezone

from .models import (
    EmissionFactor,
)


class ActivityFactorView(View):

    def get(self, request, *args, **kwargs):

        activity_id = request.GET.get("activity_id")

        factor = (
            EmissionFactor.objects
            .select_related(
                "unit",
            )
            .filter(
                activity_id=activity_id,
                is_active=True,
                effective_from__lte=timezone.now().date(),
            )
            .order_by(
                "-effective_from",
            )
            .first()
        )

        if not factor:

            return JsonResponse(
                {
                    "success": False,
                    "message": "Emission factor not found.",
                }
            )

        return JsonResponse(
            {
                "success": True,
                "factor": str(factor.emission_factor),
                "unit": factor.unit.symbol,
                "source": factor.source,
                "factor_id": factor.id,
            }
        )



from django.views import View
from django.db import transaction
from django.utils import timezone
from django.http import JsonResponse
import json


class SaveEmissionTransactionsView(View):

    @transaction.atomic
    def post(self, request):

        try:

            data = json.loads(request.body)

            company_id = data["company"]
            plant_id = data["plant"]
            fy_id = data["financial_year"]
            month_id = data["financial_month"]
            assignment_id = data.get("assignment")
            company = get_object_or_404(Company, id=company_id)
            plant = get_object_or_404(Plant, id=plant_id)
            financial_year = get_object_or_404(FinancialYear, id=fy_id)
            financial_month = get_object_or_404(FinancialMonth, id=month_id)
            assignment = None
            assigned_source_ids = set()

            # ---------------------------------------------------
            # Assignment Permission Validation
            # ---------------------------------------------------
            if assignment_id:

                assignment = get_object_or_404(EmissionAssignment,id=assignment_id,)

                is_assigner = assignment.assigner_id == request.user.id
                is_assignee = assignment.assignee_id == request.user.id

                # Reviewer can review but cannot save
                if not (is_assigner or is_assignee):
                    return JsonResponse(
                        {
                            "success": False,
                            "message": "You are not authorized to save this assignment.",
                        },
                        status=403,
                    )

                assigned_source_ids = set(
                    assignment.assignment_sources.values_list(
                        "source_id",
                        flat=True,
                    )
                )

            rows = data.get("rows", [])

            for row in rows:

                quantity = row.get("quantity", 0)

                if not quantity:
                    continue

                source_id = row["source"]

                # ---------------------------------------------------
                # Validate Source belongs to Assignment
                # ---------------------------------------------------
                if assignment and source_id not in assigned_source_ids:

                    return JsonResponse(
                        {
                            "success": False,
                            "message": f"Source {source_id} is not assigned to this assignment.",
                        },
                        status=403,
                    )

                # FIX: Include ALL identifying fields in the filter
                # This ensures we update the correct record or create a new one
                transaction_obj, created = (
                    EmissionTransaction.objects.update_or_create(
                        assignment_id=assignment_id,
                        activity_id=row["activity"],
                        source_id=source_id,
                        company_id=company_id,
                        plant_id=plant_id,
                        financial_year_id=fy_id,
                        financial_month_id=month_id,
                        defaults={
                            "unit_id": row["unit"],
                            "quantity": quantity,
                            "remarks": row.get("remarks", ""),
                            "status": "DRAFT",
                            "created_by": request.user,
                        }
                    )
                )

                # Recalculate emission
                transaction_obj.save()

            # ---------------------------------------------------
            # Update Assignment Status
            # ---------------------------------------------------
            if (
                assignment
                and assignment.assignee_id == request.user.id
                and assignment.status == "ASSIGNED"
            ):
                assignment.status = "IN_PROGRESS"
                assignment.save(update_fields=["status"])


            # ---------------------------------------------------
            # Check Goal KPIs after emission data is saved
            # ---------------------------------------------------
            try:

                goal_kpis = (
                    KPI.objects
                    .filter(
                        is_active=True,
                        goal__is_active=True,
                        goal__material_topic__is_active=True,
                    )
                    .select_related(
                        "goal",
                        "goal__material_topic",
                    )
                )

                # Users who have access to Goal module
                goal_users = (
                    User.objects
                    .filter(
                        is_active=True,
                        role__is_active=True,
                        company_id=company_id,
                        role__permissions__code="ACCESS_GOAL_MODULE",
                        role__permissions__module_name="Goal",
                        role__permissions__permission_type="MODULE_ACCESS",
                    )
                    .distinct()
                )

                for kpi in goal_kpis:

                    for recipient in goal_users:

                        GoalNotificationService.check_kpi(
                            kpi=kpi,
                            company=company,
                            recipient=recipient,
                            plant=plant,
                            financial_year=financial_year,
                            financial_month=financial_month,
                            assignment=assignment,
                        )

            except Exception as goal_error:

                # Do not fail emission saving if Goal notification
                # checking encounters an error.
                logger.exception(
                    "Goal KPI notification check failed: %s",
                    goal_error,
                )

            return JsonResponse(
                {
                    "success": True,
                    "message": "Transactions saved successfully.",
                }
            )

        except Exception as e:

            return JsonResponse(
                {
                    "success": False,
                    "message": str(e),
                },
                status=500,
            )
        

from django.db.models import Sum

from django.db.models import Sum
from django.http import JsonResponse
from django.views import View

from django.views import View
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.db.models import Sum, Q

from .models import EmissionTransaction, EmissionAssignment


class LoadEmissionTransactionsView(View):

    def get(self, request):

        company = request.GET.get("company")
        plant = request.GET.get("plant")
        financial_year = request.GET.get("financial_year")
        financial_month = request.GET.get("financial_month")
        assignment_id = request.GET.get("assignment")

        data = []

        # ----------------------------------------------------
        # Validate Assignment (only if assignment exists)
        # ----------------------------------------------------
        assignment = None

        if assignment_id:

            assignment = get_object_or_404(
                EmissionAssignment,
                id=assignment_id,
            )

            is_assigner = assignment.assigner_id == request.user.id
            is_assignee = assignment.assignee_id == request.user.id
            is_reviewer = assignment.reviewer_id == request.user.id

            if not (is_assigner or is_assignee or is_reviewer):
                return JsonResponse(
                    {
                        "success": False,
                        "message": "You are not authorized to access this assignment.",
                    },
                    status=403,
                )

        # ====================================================
        # Assignment Mode
        # ====================================================
        if assignment:

            transactions = (
                EmissionTransaction.objects
                .filter(assignment=assignment)
                .select_related("activity")
            )

            for transaction in transactions:

                data.append({
                    "activity": transaction.activity_id,
                    "source": transaction.source_id,
                    "quantity": str(transaction.quantity),
                    "factor": str(transaction.emission_factor),
                    "total": str(transaction.total_emission),
                    "status": transaction.status,
                })

        # ====================================================
        # ALL Plants
        # ====================================================
        elif plant == "ALL":

            transactions = (
                EmissionTransaction.objects
                .filter(
                    company_id=company,
                    financial_year_id=financial_year,
                    financial_month_id=financial_month,
                ).filter(
                    Q(assignment__isnull=True) |
                    Q(assignment__status="APPROVED")
                )
                .values(
                    "activity_id",
                    "source_id",
                )
                .annotate(
                    quantity=Sum("quantity"),
                    total_emission=Sum("total_emission"),
                )
                .order_by("activity_id", "source_id")
            )

            for transaction in transactions:

                # Get emission factor for display
                latest_transaction = (
                    EmissionTransaction.objects
                    .filter(
                        company_id=company,
                        financial_year_id=financial_year,
                        financial_month_id=financial_month,
                    )
                    .filter(
                        Q(assignment__isnull=True) |
                        Q(assignment__status="APPROVED")
                    )
                    .filter(
                        activity_id=transaction["activity_id"],
                        source_id=transaction["source_id"],
                    )
                    .order_by("-id")
                    .first()
                )

                data.append({
                    "activity": transaction["activity_id"],
                    "source": transaction["source_id"],
                    "quantity": str(transaction["quantity"] or 0),
                    "factor": str(
                        latest_transaction.emission_factor
                        if latest_transaction
                        else 0
                    ),
                    "total": str(transaction["total_emission"] or 0),
                    "status": (
                        latest_transaction.status
                        if latest_transaction
                        else ""
                    ),
                })
        # ====================================================
        # Single Plant
        # ====================================================
        else:

            transactions = (EmissionTransaction.objects
                .filter(company_id=company,plant_id=plant,
                    financial_year_id=financial_year,
                    financial_month_id=financial_month,
                )
                .filter(
                    Q(assignment__isnull=True) |
                    Q(assignment__status="APPROVED")
                )
                .select_related("activity")
            )

            for transaction in transactions:

                data.append({
                    "activity": transaction.activity_id,
                    "source": transaction.source_id,
                    "quantity": str(transaction.quantity),
                    "factor": str(transaction.emission_factor),
                    "total": str(transaction.total_emission),
                    "status": transaction.status,
                })

        return JsonResponse({
            "success": True,
            "transactions": data,
        })

    
class ScopeCategoriesView(View):

    def get(self, request):

        scope_code = request.GET.get("scope")

        scope = (
            EmissionScope.objects
            .prefetch_related("categories")
            .filter(code=scope_code)
            .first()
        )

        if not scope:
            return JsonResponse({
                "success": False
            })

        categories = []

        for category in scope.categories.filter(
            is_active=True
        ).order_by("display_order"):

            categories.append({
                "id": category.id,
                "name": category.name,
            })

        return JsonResponse({
            "success": True,
            "scope": scope.name,
            "description": scope.description,
            "categories": categories,
        })
    


from rest_framework.views import APIView
from rest_framework.response import Response
from apps.accounts.models import User

class PlantUsersAPIView(APIView):

    def get(self, request):

        plant_id = request.GET.get("plant_id")

        if not plant_id:
            return Response({
                "success": False,
                "assignees": [],
                "reviewers": [],
            })

        assignees = (
            User.objects.filter(
                assigned_plants__id=plant_id,
                role__role_code="DEPT-USER",
                is_active=True,
            )
            .distinct()
            .order_by("full_name", "username")
        )

        reviewers = (
            User.objects.filter(
                assigned_plants__id=plant_id,
                role__role_code="DEPT-REVIEW",
                is_active=True,
            )
            .distinct()
            .order_by("full_name", "username")
        )

        return Response({
            "success": True,

            "assignees": [
                {
                    "id": user.id,
                    "name": user.full_name or user.get_full_name() or user.username,
                    "employee_code": user.employee_code,
                    "designation": user.designation,
                    "department": user.department.name if user.department else "",
                }
                for user in assignees
            ],

            "reviewers": [
                {
                    "id": user.id,
                    "name": user.full_name or user.get_full_name() or user.username,
                    "employee_code": user.employee_code,
                    "designation": user.designation,
                    "department": user.department.name if user.department else "",
                }
                for user in reviewers
            ],
        })
    

class EmissionAssignmentDashboardViewCompact(LoginRequiredMixin, TemplateView):
    login_url = "accounts:login"
    template_name = "emission/assignment.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get assignment_id from URL parameters
        assignment_id = self.request.GET.get('assignment')
        
        # Get all assignments
        assignments = (
            EmissionAssignment.objects
            .select_related(
                "company",
                "plant",
                "financial_year",
                "financial_month",
                "scope",
                "assignee",
                "assigner",
            )
            .prefetch_related(
                "transactions",
                "assignment_sources__source__activity",
            )
            .order_by('-created_at')
        )
        
        # Validate assignment_id
        highlight_assignment_id = None
        if assignment_id:
            try:
                assignments.get(id=assignment_id)
                highlight_assignment_id = assignment_id
            except EmissionAssignment.DoesNotExist:
                pass
        
        # ====== GET TIMESHEETS ======
        # Get timesheets for the current user
        timesheets = Timesheet.objects.filter(
            models.Q(user=self.request.user) | 
            models.Q(assignment__assignee=self.request.user)
        ).filter(
            models.Q(status='assigned') | models.Q(status='viewed')
        ).select_related('assignment', 'company', 'user').order_by('-created_at')[:10]
        
        timesheet_count = timesheets.count()
        
        # ====== GET NOTIFICATIONS ======
        # Get ALL notifications (read and unread) for the dropdown
        navbar_notifications = Notification.objects.filter(
            recipient=self.request.user
        ).exclude(
            title__icontains='Timesheet'
        ).order_by('-created_at')[:10]
        
        # ✅ Count ONLY unread notifications for the badge
        navbar_notification_count = Notification.objects.filter(
            recipient=self.request.user,
            is_read=False  # ✅ Only count unread
        ).exclude(
            title__icontains='Timesheet'
        ).count()
        
        # Get stats
        today = timezone.now().date()
        assignment_stats = {
            "assignment_count": assignments.count(),
            "open_count": assignments.filter(
                status__in=["ASSIGNED", "IN_PROGRESS", "SUBMITTED"]
            ).count(),
            "completed_count": assignments.filter(status="APPROVED").count(),
            "overdue_count": assignments.filter(
                due_date__lt=today
            ).exclude(status="APPROVED").count(),
        }
        
        
        # Update context
        context.update({
            "assignments": assignments,
            "assignment_scope": "ALL ASSIGNMENTS",
            "highlight_assignment_id": highlight_assignment_id,
            "timesheets": timesheets,
            "timesheet_count": timesheet_count,
            "navbar_notifications": navbar_notifications,  # All notifications (read + unread)
            "navbar_notification_count": navbar_notification_count,  # Only unread count
            **assignment_stats,
        })
        
        return context

    def get(self, request, *args, **kwargs):
        # Check if PDF download is requested
        if request.GET.get('download_pdf'):
            from apps.emission.services.pdf_generator import generate_emission_pdf_report
            from apps.accounts.models import User
            
            # Get user with company
            user = request.user
            company_name = None
            if user.is_authenticated:
                user = User.objects.select_related('company').get(id=user.id)
                if user.company:
                    company_name = user.company.company_name
                    print(f"DEBUG: Company name from user: {company_name}")
            
            assignment_id = request.GET.get('assignment')
            
            pdf_buffer = generate_emission_pdf_report(
                assignment_id=assignment_id,
                company_name=company_name,  # Pass company name
                user=user,  # Pass user object
            )
            
            timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
            filename = f"emission_assignments_{timestamp}.pdf"
            
            response = HttpResponse(pdf_buffer.getvalue(), content_type='application/pdf')
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            return response
        
        return super().get(request, *args, **kwargs)


class EmissionAssignmentDetailView(LoginRequiredMixin, TemplateView):

    template_name = "emission/assignment_detail.html"

    def get_context_data(self, **kwargs):

        context = super().get_context_data(**kwargs)

        assignment = get_object_or_404(
            EmissionAssignment.objects.select_related(
                "company",
                "plant",
                "financial_year",
                "financial_month",
                "scope",
                "assigner",
                "assignee",
            ),
            pk=self.kwargs["assignment_id"],
            assignee=self.request.user,
        )

        assigned_sources = (
            assignment.assignment_sources
            .select_related(
                "source",
                "source__activity",
                "source__activity__category",
            )
            .order_by(
                "source__activity__category__display_order",
                "source__activity__display_order",
                "source__display_order",
            )
        )

        transactions = (
            EmissionTransaction.objects
            .filter(assignment=assignment)
            .select_related(
                "activity",
                "source",
                "unit",
            )
        )

        context["assignment"] = assignment
        context["assigned_sources"] = assigned_sources
        context["transactions"] = transactions
        
        return context

    def get(self, request, *args, **kwargs):
        # Check if PDF download is requested
        if request.GET.get('download_pdf'):
            from apps.emission.services.pdf_generator import generate_emission_pdf_report
            from apps.accounts.models import User
            
            # Get user with company
            user = request.user
            company_name = None
            if user.is_authenticated:
                user = User.objects.select_related('company').get(id=user.id)
                if user.company:
                    company_name = user.company.company_name
                    print(f"DEBUG: Company name from user: {company_name}")
            
            assignment_id = self.kwargs.get('assignment_id')
            
            pdf_buffer = generate_emission_pdf_report(
                assignment_id=assignment_id,
                company_name=company_name,  # Pass company name
                user=user,  # Pass user object
            )
            
            timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
            filename = f"emission_assignment_{assignment_id}_{timestamp}.pdf"
            
            response = HttpResponse(pdf_buffer.getvalue(), content_type='application/pdf')
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            return response
        
        return super().get(request, *args, **kwargs)








from django.views import View
from django.http import JsonResponse
from django.db import transaction
import json


from django.views import View
from django.http import JsonResponse
from django.db import transaction
from django.utils import timezone
import json

from .models import (
    EmissionAssignment,
    EmissionTransaction,
)


class SubmitAssignmentView(View):
    @transaction.atomic
    def post(self, request):

        try:

            data = json.loads(request.body)

            assignment_id = data.get("assignment")

            if not assignment_id:
                return JsonResponse({
                    "success": False,
                    "message": "Assignment not found."
                })

            assignment = (
                EmissionAssignment.objects
                .filter(
                    id=assignment_id,
                    assignee=request.user,
                )
                .first()
            )

            if not assignment:
                return JsonResponse({
                    "success": False,
                    "message": "Invalid assignment."
                })

            # Prevent duplicate submission
            if assignment.status == "SUBMITTED":
                return JsonResponse({
                    "success": False,
                    "message": "Assignment has already been submitted."
                })

            # Load all transactions for this assignment
            transactions = EmissionTransaction.objects.filter(
                assignment=assignment
            )

            if not transactions.exists():
                return JsonResponse({
                    "success": False,
                    "message": "No emission data has been entered for this assignment."
                })

            # Update all transactions
            transactions.update(
                status="SUBMITTED",
                submitted_by=request.user,
                submitted_at=timezone.now(),
            )

            # Update assignment status
            assignment.status = "SUBMITTED"
            assignment.review_comments = ""

            assignment.save(
                update_fields=[
                    "status",
                    "review_comments",
                ]
            )
            # Call the data
            context = EventContext(
                module=EMISSION,
                entity=ASSIGNMENT,
                action=SUBMITTED,
                target=assignment,
                actor=request.user,
            )
            EventService.publish(context)

            return JsonResponse({
                "success": True,
                "message": "Assignment submitted successfully."
            })

        except Exception as e:

            return JsonResponse({
                "success": False,
                "message": str(e)
            })
        






from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
import json

class CheckAssignedSourcesAPIView(APIView):

    def post(self, request):

        data = request.data

        assigned = EmissionAssignmentSource.objects.filter(
            assignment__company_id=data.get("company"),
            assignment__plant_id=data.get("plant"),
            assignment__financial_year_id=data.get("financial_year"),
            assignment__financial_month_id=data.get("financial_month"),
            assignment__assignee_id=data.get("assignee"),   # <-- Added
            source_id__in=data.get("source_ids", [])
        ).select_related(
            "assignment__assignee",
            "source"
        )

        print("Incoming source_ids:", data.get("source_ids"))
        print(
            list(
                EmissionAssignmentSource.objects.filter(
                    assignment__assignee_id=data.get("assignee")
                ).values(
                    "source_id",
                    "source__source_name",
                    "assignment__assignment_code"
                )
            )
        )

        assigned_sources = []

        for obj in assigned:

            assigned_sources.append({
                "source_id": obj.source_id,
                "assignment_id": obj.assignment_id,
                "source_name": obj.source.source_name,
                "assignee": obj.assignment.assignee.get_full_name()
            })
            print("assigned_sources", assigned_sources)
        return Response({
            "success": True,
            "assigned_sources": assigned_sources
        })
    










from django.contrib.auth.mixins import LoginRequiredMixin
from django.views import View
from django.shortcuts import render

from .models import EmissionAssignmentSchedule


class EmissionSchedulerDashboardView(LoginRequiredMixin, View):

    template_name = "emission/scheduler_dashboard.html"

    def get(self, request):

        schedules = (
            EmissionAssignmentSchedule.objects
            .select_related(
                "company",
                "plant",
                "scope",
                "assignee",
            )
            .prefetch_related(
                "generated_assignments",
            )
            .order_by("next_run_date")
        )

        context = {
            "schedules": schedules,
        }

        return render(
            request,
            self.template_name,
            context,
        )