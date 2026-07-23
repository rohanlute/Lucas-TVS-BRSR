from django.contrib.auth import get_user_model
from django.db import transaction
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

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
)

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
        





class ApproveAssignmentView(APIView):

    @transaction.atomic
    def post(self, request):

        assignment_id = request.data.get("assignment")

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
            status="APPROVED"
        )

        assignment.status = "APPROVED"
        assignment.save(update_fields=["status"])

        return Response(
            {
                "success": True,
                "message": "Assignment approved successfully."
            }
        )
    



class RejectAssignmentView(APIView):

    @transaction.atomic
    def post(self, request):
        
        assignment_id = request.data.get("assignment")
        remarks = request.data.get("remarks", "").strip()

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

        assignment.review_comments = remarks
        assignment.status = "IN_PROGRESS"

        assignment.save(update_fields=["status","review_comments",])

        return Response(
            {
                "success": True,
                "message": "Assignment rejected."
            }
        )