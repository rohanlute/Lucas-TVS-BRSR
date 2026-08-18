from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from django.shortcuts import get_object_or_404
from apps.organizations.models import (
    FinancialMonth,
    FinancialYear,
    Plant,
)

from .models import (
    EmissionAssignment,
    EmissionScope,
    EmissionCategory,
    EmissionActivity,
    EmissionSource,
    EmissionTransaction,
)

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.db import transaction
from .models import (
    EmissionAssignment,
    EmissionTransaction,
    EmissionAssignmentSchedule,
)
from .forms_schedule import EmissionAssignmentScheduleForm
from .utils import generate_schedule_code

# Notication and Timesheet 
from apps.common_events.event_context import EventContext
from apps.common_events.constants import *
from apps.common_events.services import EventService

User = get_user_model()


class EmissionAssignmentCreateAPIView(APIView):

    @transaction.atomic
    def post(self, request):

        try:
            data = request.data

            plant = Plant.objects.get(pk=data["plant"])

            financial_year = FinancialYear.objects.get(pk=data["financial_year"])

            financial_month = FinancialMonth.objects.get(pk=data["financial_month"])

            scope = EmissionScope.objects.get(pk=data["scope"])

            assignee = User.objects.get(pk=data["assignee"])

            # Check if assignment already exists
            if EmissionAssignment.objects.filter(
                company=plant.created_by.company,
                plant=plant,
                financial_year=financial_year,
                financial_month=financial_month,
                scope=scope,
            ).exists():

                return Response(
                    {
                        "success": False,
                        "message": "Assignment already exists for the selected Plant, Financial Year, Financial Month and Scope."
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Generate Assignment Code
            last_assignment = (EmissionAssignment.objects.order_by("-id").first())

            if last_assignment:
                next_number = last_assignment.id + 1
            else:
                next_number = 1

            assignment_code = f"EA-{next_number:05d}"

            assignment = EmissionAssignment.objects.create(

                assignment_code=assignment_code,

                company=plant.created_by.company,

                plant=plant,

                financial_year=financial_year,

                financial_month=financial_month,

                scope=scope,

                assigner=request.user,

                assignee=assignee,

                due_date=data.get("due_date"),

                frequency=data.get("frequency"),

                priority=data.get("priority", "MEDIUM"),

                notes=data.get("notes", ""),

            )

            activities = (
                EmissionActivity.objects.filter(
                    category__scope=scope,
                    is_active=True,
                    category__is_active=True,
                )
                .select_related("base_unit")
                .prefetch_related("sources")
            )

            for activity in activities:

                sources = activity.sources.filter(is_active=True)

                for source in sources:

                    EmissionTransaction.objects.create(

                        assignment=assignment,

                        company=assignment.company,

                        plant=assignment.plant,

                        financial_year=assignment.financial_year,

                        financial_month=assignment.financial_month,

                        activity=activity,

                        source=source,

                        unit=activity.base_unit,

                        quantity=0,

                        remarks="",

                        created_by=request.user,
                    )

            return Response(
                {
                    "success": True,
                    "message": "Assignment created successfully.",
                    "assignment_id": assignment.id,
                    "assignment_code": assignment.assignment_code,
                    "transaction_count": assignment.transactions.count(),
                },
                status=status.HTTP_201_CREATED,
            )

        except Plant.DoesNotExist:
            return Response(
                {
                    "success": False,
                    "message": "Plant not found."
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        except FinancialYear.DoesNotExist:
            return Response(
                {
                    "success": False,
                    "message": "Financial Year not found."
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        except FinancialMonth.DoesNotExist:
            return Response(
                {
                    "success": False,
                    "message": "Financial Month not found."
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        except EmissionScope.DoesNotExist:
            return Response(
                {
                    "success": False,
                    "message": "Emission Scope not found."
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        except User.DoesNotExist:
            return Response(
                {
                    "success": False,
                    "message": "Assignee not found."
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        except Exception as e:
            return Response(
                {
                    "success": False,
                    "message": str(e),
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        

class CoordinatorApproveAssignmentView(APIView):

    @transaction.atomic
    def post(self, request):

        assignment_id = request.data.get("assignment")
        comments = request.data.get("comments", "").strip()

        if not assignment_id:
            return Response(
                {
                    "success": False,
                    "message": "Assignment not found."
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            assignment = EmissionAssignment.objects.get(
                id=assignment_id,
                assigner=request.user,
                status="REVIEW_APPROVED",
            )

        except EmissionAssignment.DoesNotExist:
            return Response(
                {
                    "success": False,
                    "message": "Assignment does not exist."
                },
                status=status.HTTP_404_NOT_FOUND
            )

        EmissionTransaction.objects.filter(
            assignment=assignment
        ).update(
            status="APPROVED",
            approved_by=request.user,
            approved_at=timezone.now(),
        )

        assignment.status = "APPROVED"
        assignment.coordinator_comments = comments

        assignment.save(
            update_fields=[
                "status",
                "coordinator_comments",
            ]
        )
        context = EventContext(
            module=EMISSION,
            entity=ASSIGNMENT,
            action=FINAL_APPROVED,
            target=assignment,
            actor=request.user,
        )

        EventService.publish(context)
        return Response(
            {
                "success": True,
                "message": "Assignment approved successfully."
            }
        )


class CoordinatorRejectAssignmentView(APIView):

    @transaction.atomic
    def post(self, request):

        assignment_id = request.data.get("assignment")
        comments = request.data.get("comments", "").strip()

        if not assignment_id:
            return Response(
                {
                    "success": False,
                    "message": "Assignment not found."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            assignment = EmissionAssignment.objects.get(
                id=assignment_id,
                assigner=request.user,
                status="REVIEW_APPROVED",
            )

        except EmissionAssignment.DoesNotExist:
            return Response(
                {
                    "success": False,
                    "message": "Assignment does not exist."
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        EmissionTransaction.objects.filter(
            assignment=assignment
        ).update(
            status="DRAFT"
        )

        assignment.status = "IN_PROGRESS"
        assignment.coordinator_comments = comments

        assignment.save(
            update_fields=[
                "status",
                "coordinator_comments",
            ]
        )

        context = EventContext(
            module=EMISSION,
            entity=ASSIGNMENT,
            action=FINAL_REJECTED,
            target=assignment,
            actor=request.user,
        )

        EventService.publish(context)

        return Response(
            {
                "success": True,
                "message": "Assignment returned to Department User."
            }
        )

class ApproveAssignmentView(APIView):

    @transaction.atomic
    def post(self, request):

        assignment_id = request.data.get("assignment")
        comments = request.data.get("comments", "").strip()

        if not assignment_id:
            return Response(
                {
                    "success": False,
                    "message": "Assignment not found."
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            assignment = EmissionAssignment.objects.get(
                id=assignment_id,
                reviewer=request.user,
                status="SUBMITTED",
            )

        except EmissionAssignment.DoesNotExist:
            return Response(
                {
                    "success": False,
                    "message": "Assignment does not exist."
                },
                status=status.HTTP_404_NOT_FOUND
            )

        assignment.status = "REVIEW_APPROVED"
        assignment.review_comments = comments
        assignment.reviewer = request.user

        assignment.save(
            update_fields=[
                "status",
                "review_comments",
                "reviewer",
            ]
        )

        context = EventContext(
            module=EMISSION,
            entity=ASSIGNMENT,
            action=REVIEW_APPROVED,
            target=assignment,
            actor=request.user,
        )
        EventService.publish(context)

        return Response(
            {
                "success": True,
                "message": "Assignment sent to ESG Coordinator for approval."
            }
        )
    



class RejectAssignmentView(APIView):

    @transaction.atomic
    def post(self, request):
        
        assignment_id = request.data.get("assignment")
        remarks = request.data.get("remarks", "").strip()
        comments = request.data.get("comments", "").strip()

        if not assignment_id:
            return Response(
                {
                    "success": False,
                    "message": "Assignment not found."
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        try:

            assignment = EmissionAssignment.objects.get(
                id=assignment_id
            )

        except EmissionAssignment.DoesNotExist:

            return Response(
                {
                    "success": False,
                    "message": "Assignment does not exist."
                },
                status=status.HTTP_404_NOT_FOUND
            )

        EmissionTransaction.objects.filter(
            assignment=assignment
        ).update(
            status="DRAFT"
        )

        assignment.review_comments = comments
        assignment.reviewer = request.user
        assignment.status = "IN_PROGRESS"

        assignment.save(
            update_fields=[
                "status",
                "review_comments",
                "reviewer",
            ]
        )

        context = EventContext(
            module=EMISSION,
            entity=ASSIGNMENT,
            action=REVIEW_REJECTED,
            target=assignment,
            actor=request.user,
        )
        EventService.publish(context)


        return Response(
            {
                "success": True,
                "message": "Assignment rejected."
            }
        )



from .models import (EmissionAssignmentScheduleSource,)
class SaveEmissionScheduleAPIView(APIView):

    @transaction.atomic
    def post(self, request):

        form = EmissionAssignmentScheduleForm(data=request.data)

        if not form.is_valid():
            return Response(
                {
                    "success": False,
                    "errors": form.errors,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        schedule = form.save(commit=False)

        schedule.schedule_code = generate_schedule_code()

        # Save the converted months from the form
        schedule.selected_months = form.cleaned_data.get(
            "selected_months",
            []
        )

        # First execution date
        schedule.next_run_date = schedule.start_date

        schedule.save()
        # ----------------------------------------
        # Save Selected Emission Sources
        # ----------------------------------------

        for source in form.cleaned_data["source_ids"]:

            EmissionAssignmentScheduleSource.objects.create(
                schedule=schedule,
                source=source,
            )

        return Response(
            {
                "success": True,
                "message": "Schedule created successfully.",
                "schedule_id": schedule.id,
                "schedule_code": schedule.schedule_code,
            },
            status=status.HTTP_201_CREATED,
        )
    





class EmissionScheduleListAPIView(APIView):

    def get(self, request):

        schedules = (
            EmissionAssignmentSchedule.objects
            .select_related(
                "company",
                "plant",
                "scope",
                "assigner",
                "assignee",
                "reviewer",
            )
            .order_by("-created_at")
        )

        data = []

        for schedule in schedules:

            data.append({

                "id": schedule.id,

                "schedule_code": schedule.schedule_code,

                "name": schedule.name,

                "company": schedule.company.company_name,

                "plant": schedule.plant.name,

                "scope": schedule.scope.name,

                "assigner": schedule.assigner.get_full_name() or schedule.assigner.username,

                "assignee": schedule.assignee.get_full_name() or schedule.assignee.username,

                "reviewer": (
                    schedule.reviewer.get_full_name() or schedule.reviewer.username
                ) if schedule.reviewer else "-",

                "schedule_type": schedule.get_schedule_type_display(),

                "frequency": (
                    schedule.get_frequency_display()
                    if schedule.frequency
                    else "-"
                ),

                "start_date": schedule.start_date,

                "end_date": schedule.end_date,

                "next_run_date": schedule.next_run_date,

                "last_run_date": schedule.last_run_date,

                "status": schedule.status,

                "priority": schedule.priority,

                "total_assignments_created": schedule.total_assignments_created,

            })

        return Response(
            {
                "success": True,
                "count": len(data),
                "data": data,
            },
            status=status.HTTP_200_OK,
        )



class UpdateEmissionScheduleAPIView(APIView):

    @transaction.atomic
    def post(self, request, schedule_id):

        schedule = get_object_or_404(
            EmissionAssignmentSchedule,
            id=schedule_id,
        )

        form = EmissionAssignmentScheduleForm(
            data=request.data,
            instance=schedule,
        )

        if not form.is_valid():
            return Response(
                {
                    "success": False,
                    "errors": form.errors,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        schedule = form.save()

        return Response(
            {
                "success": True,
                "message": "Schedule updated successfully.",
            },
            status=status.HTTP_200_OK,
        )


class ToggleEmissionScheduleAPIView(APIView):

    @transaction.atomic
    def post(self, request, schedule_id):

        schedule = get_object_or_404(
            EmissionAssignmentSchedule,
            id=schedule_id,
        )

        if schedule.status == "ACTIVE":

            schedule.status = "PAUSED"
            schedule.is_active = False

        elif schedule.status == "PAUSED":

            schedule.status = "ACTIVE"
            schedule.is_active = True

        schedule.save(
            update_fields=[
                "status",
                "is_active",
            ]
        )

        return Response(
            {
                "success": True,
                "status": schedule.status,
                "message": f"Schedule {schedule.status.lower()} successfully.",
            }
        )

    


class DeleteEmissionScheduleAPIView(APIView):

    @transaction.atomic
    def delete(self, request, schedule_id):

        schedule = get_object_or_404(EmissionAssignmentSchedule,id=schedule_id,)

        schedule.delete()

        return Response(
            {
                "success": True,
                "message": "Schedule deleted successfully.",
            }
        )



from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from .models import EmissionAssignmentSchedule


class ToggleScheduleStatusAPIView(APIView):

    def post(self, request):

        schedule_id = request.data.get("schedule_id")

        try:

            schedule = EmissionAssignmentSchedule.objects.get(
                id=schedule_id
            )

        except EmissionAssignmentSchedule.DoesNotExist:

            return Response(
                {
                    "success": False,
                    "message": "Schedule not found.",
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        if schedule.is_active:

            schedule.is_active = False
            schedule.status = "PAUSED"

        else:

            schedule.is_active = True
            schedule.status = "ACTIVE"

        schedule.save(
            update_fields=[
                "is_active",
                "status",
            ]
        )

        return Response(
            {
                "success": True,
                "status": schedule.status,
                "is_active": schedule.is_active,
                "message": f"Schedule {schedule.status.lower()} successfully.",
            }
        )






from rest_framework.views import APIView
from rest_framework.response import Response

from .models import EmissionAssignmentSchedule


class ScheduleHistoryAPIView(APIView):

    def get(self, request, schedule_id):

        try:
            schedule = (
                EmissionAssignmentSchedule.objects
                .prefetch_related(
                    "generated_assignments__financial_year",
                    "generated_assignments__financial_month",
                    "generated_assignments__assignee",
                )
                .get(id=schedule_id)
            )

        except EmissionAssignmentSchedule.DoesNotExist:

            return Response(
                {
                    "success": False,
                    "message": "Schedule not found.",
                },
                status=404,
            )

        data = []

        for assignment in schedule.generated_assignments.order_by("-created_at"):

            data.append({
                "assignment_code": assignment.assignment_code,
                "financial_year": str(assignment.financial_year),
                "financial_month": str(assignment.financial_month),
                "assignee": assignment.assignee.get_full_name()
                if assignment.assignee else "",
                "status": assignment.status,
                "created_at": assignment.created_at.strftime("%d-%b-%Y"),
            })

        return Response({
            "success": True,
            "schedule": schedule.schedule_code,
            "history": data,
        })
    

from decimal import Decimal
from datetime import timedelta
from django.http import JsonResponse

from .models import EmissionTransaction
from apps.organizations.models import FinancialYear


def ScopeTotalsAPIView(request):

    company_id = request.GET.get("company")
    plant_id = request.GET.get("plant")
    financial_year_id = request.GET.get("financial_year")
    financial_month_id = request.GET.get("financial_month")

    if not all([
        company_id,
        plant_id,
        financial_year_id,
        financial_month_id
    ]):
        return JsonResponse({
            "success": False,
            "message": "Missing required filters."
        })

    # ==========================================================
    # CURRENT FINANCIAL YEAR
    # ==========================================================

    try:
        current_fy = FinancialYear.objects.get(
            id=financial_year_id
        )
    except FinancialYear.DoesNotExist:

        return JsonResponse({
            "success": False,
            "message": "Financial year not found."
        })

    # ==========================================================
    # FIND PREVIOUS FINANCIAL YEAR
    # ==========================================================

    previous_fy = FinancialYear.objects.filter(
        start_date__lt=current_fy.start_date
    ).order_by("-start_date").first()

    print("CURRENT FY:", current_fy.financial_year)
    print("CURRENT FY START:", current_fy.start_date)

    if previous_fy:
        print("PREVIOUS FY:", previous_fy.financial_year)
        print("PREVIOUS FY START:", previous_fy.start_date)
        print("PREVIOUS FY END:", previous_fy.end_date)
    else:
        print("NO PREVIOUS FINANCIAL YEAR FOUND")

    # ==========================================================
    # CURRENT YEAR TRANSACTIONS
    # ==========================================================

    current_transactions = EmissionTransaction.objects.filter(
        company_id=company_id,
        financial_year_id=current_fy.id,
        financial_month_id=financial_month_id,
    )

    # ==========================================================
    # PLANT FILTER
    # ==========================================================

    if plant_id != "ALL":

        current_transactions = current_transactions.filter(
            plant_id=plant_id
        )

    else:

        allowed_plant_ids = request.user.assigned_plants.values_list(
            "id",
            flat=True
        )

        current_transactions = current_transactions.filter(
            plant_id__in=allowed_plant_ids
        )

    # ==========================================================
    # PREVIOUS YEAR TRANSACTIONS
    # ==========================================================

    previous_transactions = EmissionTransaction.objects.none()

    if previous_fy:

        previous_transactions = EmissionTransaction.objects.filter(
            company_id=company_id,
            financial_year_id=previous_fy.id,
            financial_month_id=financial_month_id,
        )

        if plant_id != "ALL":

            previous_transactions = previous_transactions.filter(
                plant_id=plant_id
            )

        else:

            previous_transactions = previous_transactions.filter(
                plant_id__in=allowed_plant_ids
            )

    # ==========================================================
    # INITIAL TOTALS
    # ==========================================================

    current_totals = {
        "S1": Decimal("0"),
        "S2": Decimal("0"),
        "S3": Decimal("0"),
    }

    previous_totals = {
        "S1": None,
        "S2": None,
        "S3": None,
    }

    # ==========================================================
    # CURRENT YEAR CALCULATION
    # ==========================================================

    for transaction in current_transactions.select_related(
        "activity__category__scope"
    ):

        scope_code = transaction.activity.category.scope.code

        if scope_code in current_totals:

            current_totals[scope_code] += (
                transaction.total_emission or Decimal("0")
            )

    # ==========================================================
    # PREVIOUS YEAR CALCULATION
    # ==========================================================

    if previous_fy:

        previous_totals = {
            "S1": Decimal("0"),
            "S2": Decimal("0"),
            "S3": Decimal("0"),
        }

        for transaction in previous_transactions.select_related(
            "activity__category__scope"
        ):

            scope_code = transaction.activity.category.scope.code

            if scope_code in previous_totals:

                previous_totals[scope_code] += (
                    transaction.total_emission or Decimal("0")
                )

        # If there are no previous-year transactions at all,
        # return None instead of showing 0 as previous data.
        if not previous_transactions.exists():

            previous_totals = {
                "S1": None,
                "S2": None,
                "S3": None,
            }

    # ==========================================================
    # RESPONSE
    # ==========================================================

    return JsonResponse({

        "success": True,

        "current": {
            "S1": float(
                current_totals["S1"] / Decimal("1000")
            ),
            "S2": float(
                current_totals["S2"] / Decimal("1000")
            ),
            "S3": float(
                current_totals["S3"] / Decimal("1000")
            ),
        },

        "previous": {
            "S1": (
                float(previous_totals["S1"] / Decimal("1000"))
                if previous_totals["S1"] is not None
                else None
            ),
            "S2": (
                float(previous_totals["S2"] / Decimal("1000"))
                if previous_totals["S2"] is not None
                else None
            ),
            "S3": (
                float(previous_totals["S3"] / Decimal("1000"))
                if previous_totals["S3"] is not None
                else None
            ),
        },

        "current_year": current_fy.financial_year,

        "previous_year": (
            previous_fy.financial_year
            if previous_fy
            else None
        ),
    })