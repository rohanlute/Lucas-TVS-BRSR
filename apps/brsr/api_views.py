from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.shortcuts import get_object_or_404
from django.urls import reverse
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from apps.organizations.models import FinancialYear, Plant
from .forms import BRSRAssignmentForm
from .models import Assignment, BRSRPrinciple, BRSRQuestion, BRSRSection, QuestionResponse
from .views import (
    _assignment_context,
    _assignment_target_role_codes,
    _default_assignee_for_context,
    _get_assignment_scope,
    _get_section_principle,
    _plant_assignees,
    _pdf_questions_queryset,
    _question_metadata,
    _question_queryset,
    _question_status,
    _workflow_counts,
)


User = get_user_model()


def _serialize_section(section):
    return {
        "code": section.code,
        "name": section.name,
        "display_order": section.display_order,
        "url": reverse("brsr:question_workspace_section", kwargs={"section_code": section.code}),
    }


def _serialize_principle(principle):
    return {
        "slug": principle.slug,
        "number": principle.principle_number,
        "name": principle.principle_name,
        "title": principle.title,
        "url": reverse(
            "brsr:question_workspace_principle",
            kwargs={"section_code": "section_c", "principle_slug": principle.slug},
        ),
    }


def _serialize_question(question):
    response = (
        QuestionResponse.objects.filter(question=question)
        .select_related("assignment")
        .order_by("-updated_at", "-created_at")
        .first()
    )
    return {
        "question_id": question.question_id,
        "title": question.question_text,
        "question_number": question.question_number,
        "question_type": question.question_type,
        "status": response.status if response else "draft",
        "section_code": question.section.code,
        "sub_section": question.sub_section or "",
        "help_text": question.help_text or "",
        "is_required": question.is_required,
        "display_order": question.display_order,
        "placeholder_text": question.placeholder_text or "",
        "options": question.options or [],
        "validation_rules": question.validation_rules or {},
        **_question_metadata(question),
        "response_value": response.response_value if response else "",
        "response_json": response.response_json if response else {},
        "is_editable": response.is_editable if response else True,
        "assignment_id": response.assignment.assignment_id if response else "",
    }


def _serialize_user(user):
    return {
        "id": user.id,
        "name": user.full_name or user.get_full_name() or user.username,
        "username": user.username,
        "department_id": user.department_id,
        "department_name": user.department.name if user.department_id else "",
        "role_code": getattr(getattr(user, "role", None), "role_code", "") or "",
    }


class BRSRWorkspaceDataAPIView(APIView):
    def get(self, request):
        section_code = request.query_params.get("section_code")
        principle_slug = request.query_params.get("principle_slug")
        question_id = request.query_params.get("question_id")

        section, principle = _get_section_principle(section_code, principle_slug)
        if not section:
            return Response({"detail": "No BRSR section found."}, status=status.HTTP_404_NOT_FOUND)

        questions = list(_question_queryset(section, principle))
        active_question = None
        if question_id:
            active_question = next((q for q in questions if q.question_id == question_id), None)
        if active_question is None and questions:
            active_question = questions[0]

        section_cards = list(BRSRSection.objects.filter(is_active=True).order_by("display_order", "code"))
        principle_cards = list(BRSRPrinciple.objects.filter(is_active=True).order_by("principle_number"))

        assignment_bundle = _assignment_context(
            section,
            principle,
            _pdf_questions_queryset().filter(id__in=[q.id for q in questions]),
        )

        payload = {
            "section": _serialize_section(section),
            "principle": _serialize_principle(principle) if principle else None,
            "assignment_scope": _get_assignment_scope(request.user),
            "current_user_id": request.user.id,
            "current_user_name": request.user.full_name or request.user.get_full_name() or request.user.username,
            "sections": [_serialize_section(item) for item in section_cards],
            "principles": [_serialize_principle(item) for item in principle_cards],
            "topics": [_serialize_question(question) for question in questions],
            "active_question": _serialize_question(active_question) if active_question else None,
            "active_question_id": active_question.question_id if active_question else "",
            "counts": _workflow_counts(questions),
            "plants": [
                {"id": plant.id, "name": plant.name, "code": plant.code}
                for plant in assignment_bundle["plants"]
            ],
            "users": [
                {
                    "id": user.id,
                    "name": user.full_name or user.get_full_name() or user.username,
                    "username": user.username,
                }
                for user in assignment_bundle["users"]
            ],
            "financial_years": [
                {"value": fy.financial_year, "label": fy.financial_year}
                for fy in assignment_bundle["financial_years"]
            ],
            "frequency_choices": [
                {"value": value, "label": label}
                for value, label in Assignment.FREQUENCY_CHOICES
            ],
            # parent_assignments removed from payload — delegation not used
            "latest_assignment": (
                {
                    "id": assignment_bundle["latest_assignment"].id,
                    "assignment_id": assignment_bundle["latest_assignment"].assignment_id,
                    "plant": assignment_bundle["latest_assignment"].plant.name,
                    "assignee": str(assignment_bundle["latest_assignment"].assignee),
                    "parent_id": assignment_bundle["latest_assignment"].parent_id,
                }
                if assignment_bundle["latest_assignment"]
                else None
            ),
        }
        return Response(payload)


class AssignmentOptionsAPIView(APIView):
    def get(self, request):
        plant_id = request.query_params.get("plant_id")
        if not plant_id:
            return Response({"detail": "plant_id is required."}, status=status.HTTP_400_BAD_REQUEST)

        plant = get_object_or_404(Plant, pk=plant_id, is_active=True)
        target_role_codes = _assignment_target_role_codes(request.user)
        assignees = _plant_assignees(plant, target_role_codes=target_role_codes, current_user=request.user)
        default_assignee = _default_assignee_for_context(request.user, plant)

        return Response(
            {
                "plant": {"id": plant.id, "name": plant.name, "code": plant.code},
                "scope": _get_assignment_scope(request.user),
                "assignees": [_serialize_user(item) for item in assignees],
                "default_assignee": _serialize_user(default_assignee) if default_assignee else None,
                "target_role_codes": target_role_codes,
            }
        )


class QuestionDetailAPIView(APIView):
    def get(self, request, question_id):
        question = get_object_or_404(_pdf_questions_queryset().select_related("section", "principle"), question_id=question_id)
        return Response(_serialize_question(question))


class QuestionSaveAPIView(APIView):
    def put(self, request, question_id):
        question = get_object_or_404(_pdf_questions_queryset(), question_id=question_id)
        assignment_id = request.data.get("assignment_id")
        if not assignment_id:
            return Response(
                {"detail": "Create an assignment before saving this response."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        assignment = get_object_or_404(Assignment, pk=assignment_id)
        response, _ = QuestionResponse.objects.get_or_create(
            assignment=assignment,
            question=question,
        )
        if not response.is_editable:
            return Response(
                {"detail": "This response is locked and cannot be edited."},
                status=status.HTTP_409_CONFLICT,
            )
        if "response_value" in request.data:
            response.response_value = request.data.get("response_value") or ""
        if "response_json" in request.data:
            response.response_json = request.data.get("response_json") or {}
        response.save()
        return Response(_serialize_question(question))


class QuestionSubmitAPIView(APIView):
    def post(self, request, question_id):
        question = get_object_or_404(_pdf_questions_queryset(), question_id=question_id)
        assignment_id = request.data.get("assignment_id")
        if not assignment_id:
            return Response(
                {"detail": "Create an assignment before submitting this response."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        assignment = get_object_or_404(Assignment, pk=assignment_id)
        response = get_object_or_404(QuestionResponse, assignment=assignment, question=question)
        response.submit(request.user)
        return Response({"status": response.status})


class AssignmentCreateAPIView(APIView):
    def post(self, request):
        section_code = request.data.get("section_code")
        principle_slug = request.data.get("principle_slug")
        question_ids = request.data.get("question_ids", [])

        section, principle = _get_section_principle(section_code, principle_slug)
        if not section:
            return Response({"detail": "No BRSR section found."}, status=status.HTTP_404_NOT_FOUND)

        questions = _pdf_questions_queryset().filter(question_id__in=question_ids, section=section)
        if principle:
            questions = questions.filter(principle=principle)
        else:
            questions = questions.filter(principle__isnull=True)

        form = BRSRAssignmentForm(
            request.data,
            plant_queryset=Plant.objects.filter(is_active=True).order_by("name"),
            user_queryset=User.objects.filter(is_active=True).select_related("role", "department").order_by(
                "full_name", "username"
            ),
            question_queryset=questions,
            financial_year_queryset=FinancialYear.objects.all().order_by("-start_date"),
        )
        if not form.is_valid():
            return Response(form.errors, status=status.HTTP_400_BAD_REQUEST)

        user_ct = ContentType.objects.get_for_model(User)
        plant = form.cleaned_data["plant"]
        assigner = form.cleaned_data.get("assigner") or request.user
        assignee = form.cleaned_data["assignee"]
        eligible_assignees = _plant_assignees(
            plant,
            target_role_codes=_assignment_target_role_codes(request.user),
            current_user=request.user,
        )
        if assignee not in eligible_assignees:
            assignee = _default_assignee_for_context(request.user, plant)
        if assignee is None:
            return Response({"detail": "No eligible assignee found for the selected plant."}, status=status.HTTP_400_BAD_REQUEST)

        assignment = Assignment.objects.create(
            plant=plant,
            principle=principle,
            section=section,
            financial_year=form.cleaned_data["financial_year"],
            # parent assignment removed from creation flow
            data_collection_frequency=form.cleaned_data.get("data_collection_frequency") or "",
            assigner_content_type=user_ct,
            assigner_object_id=assigner.pk,
            assignee_content_type=user_ct,
            assignee_object_id=assignee.pk,
            due_date=form.cleaned_data.get("due_date"),
            priority=form.cleaned_data["priority"],
            notes=form.cleaned_data.get("notes"),
        )
        selected_questions = form.cleaned_data["question_ids"]
        assignment.questions.set(selected_questions)
        for question in selected_questions:
            QuestionResponse.objects.get_or_create(assignment=assignment, question=question)

        return Response(
            {
                "id": assignment.id,
                "assignment_id": assignment.assignment_id,
                "question_count": selected_questions.count(),
            },
            status=status.HTTP_201_CREATED,
        )
