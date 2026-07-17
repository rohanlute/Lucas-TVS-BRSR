from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from apps.organizations.models import FinancialYear, Plant
from apps.organizations.workflow_configuration_engine import WorkflowConfigurationEngine
from .forms import BRSRAssignmentForm
from .models import Assignment, BRSRPrinciple, BRSRQuestion, BRSRSection, QuestionResponse
from .views import (
    _assignment_context,
    _assignment_queryset_for_user,
    _default_assignee_for_context,
    _first_workflow_assignee_for_stage,
    _get_assignment_scope,
    _get_section_principle,
    _company_scope_plants,
    _plant_assignees,
    _workflow_assignees_for_stage,
    _pdf_questions_queryset,
    _question_metadata,
    _question_queryset,
    _question_status,
    _create_brsr_assignment,
    _workflow_entry_stage,
    _workflow_stage_by_type,
    _resolve_brsr_assignee,
    _resolve_brsr_reviewer,
    _resolve_brsr_workflow_template,
    _serialize_workflow_task,
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


def _serialize_question(question, assignment=None, user=None):
    response_qs = QuestionResponse.objects.filter(question=question)
    if assignment is not None:
        response_qs = response_qs.filter(assignment=assignment)
    response = response_qs.select_related("assignment").order_by("-updated_at", "-created_at").first()
    task = None
    if assignment and assignment.workflow_task:
        task = assignment.workflow_task
    elif response and response.workflow_task:
        task = response.workflow_task
    task_info = _serialize_task_for_user(task, user) if (task and user) else None
    workflow_stage_type = task_info.get("stage_type", "") if task_info else ""
    can_act = task_info.get("can_act", False) if task_info else False
    return {
        "question_id": question.question_id,
        "title": question.question_text,
        "question_number": question.question_number,
        "question_type": question.question_type,
        "status": response.status if response else "draft",
        "workflow_stage": task.current_stage.label if task and task.current_stage_id else "",
        "workflow_stage_type": workflow_stage_type,
        "can_act": can_act,
        "workflow_task": _serialize_workflow_task(task) if task else None,
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
        "review_remark": response.review_remark if response else "",
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


def _serialize_task_for_user(task, user):
    if not task:
        return None
    assignee_id = task.current_assignee_object_id if task.current_assignee_content_type_id and task.current_assignee_content_type.model == "user" else None
    current_user_role_id = getattr(user, "role_id", None)
    current_stage_role_id = task.current_stage.role_id if task.current_stage_id else None
    can_act = bool(
        user.is_authenticated
        and (
            user.is_superuser
            or getattr(user, "is_super_admin", False)
            or assignee_id == user.id
            or (current_user_role_id and current_stage_role_id and current_user_role_id == current_stage_role_id)
        )
    )
    return {
        "id": task.id,
        "stage": task.current_stage.label if task.current_stage_id else "",
        "stage_type": task.current_stage.stage_type if task.current_stage_id else "",
        "stage_role_code": task.current_stage.role.role_code if task.current_stage_id and task.current_stage.role_id else "",
        "current_assignee_id": assignee_id,
        "current_assignee": str(task.current_assignee) if task.current_assignee else "",
        "can_act": can_act,
    }


class BRSRWorkspaceDataAPIView(APIView):
    def get(self, request):
        section_code = request.query_params.get("section_code")
        principle_slug = request.query_params.get("principle_slug")
        question_id = request.query_params.get("question_id")
        assignment_id = request.query_params.get("assignment_id")

        section, principle = _get_section_principle(section_code, principle_slug)
        if not section:
            return Response({"detail": "No BRSR section found."}, status=status.HTTP_404_NOT_FOUND)

        assignment = None
        if assignment_id:
            assignment = (
                Assignment.objects.select_related("plant", "section", "principle", "workflow_template")
                .prefetch_related("questions", "questions__section", "questions__principle", "responses")
                .filter(pk=assignment_id)
                .first()
            )

        if assignment:
            from .views import _ensure_assignment_workflow_task
            _ensure_assignment_workflow_task(assignment, current_user=request.user)
            questions = list(
                assignment.questions.filter(section=section)
                .select_related("section", "principle", "parent_question")
                .order_by("display_order", "question_number")
            )
            if section.code == "section_c" and principle:
                questions = [question for question in questions if question.principle_id == principle.id]
            elif section.code != "section_c":
                questions = [question for question in questions if question.principle_id is None]
        else:
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
            user=request.user,
        )
        can_act = False
        workflow_stage_type = ""
        if assignment and assignment.workflow_task:
            task_info = _serialize_task_for_user(assignment.workflow_task, request.user)
            if task_info:
                can_act = task_info.get("can_act", False)
                workflow_stage_type = task_info.get("stage_type", "")

        payload = {
            "section": _serialize_section(section),
            "principle": _serialize_principle(principle) if principle else None,
            "assignment_scope": _get_assignment_scope(request.user),
            "current_user_id": request.user.id,
            "current_user_name": request.user.full_name or request.user.get_full_name() or request.user.username,
            "assignment_id": assignment_id or "",
            "sections": [_serialize_section(item) for item in section_cards],
            "principles": [_serialize_principle(item) for item in principle_cards],
            "topics": [_serialize_question(question, assignment=assignment, user=request.user) for question in questions],
            "active_question": _serialize_question(active_question, assignment=assignment, user=request.user) if active_question else None,
            "active_question_id": active_question.question_id if active_question else "",
            "counts": _workflow_counts(questions, assignment=assignment),
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
                    "workflow_template": assignment_bundle["latest_assignment"].workflow_template_name,
                    "workflow_stage": assignment_bundle["latest_assignment"].workflow_stage_label,
                    "workflow_task": _serialize_workflow_task(assignment_bundle["latest_assignment"].workflow_task),
                }
                if assignment_bundle["latest_assignment"]
                else None
            ),
            "current_assignment": (
                {
                    "id": assignment.id,
                    "assignment_id": assignment.assignment_id,
                    "workflow_template": assignment.workflow_template_name,
                    "workflow_stage": assignment.workflow_stage_label,
                    "workflow_stage_type": workflow_stage_type,
                    "current_assignee_id": assignment.workflow_task.current_assignee_object_id if assignment.workflow_task and assignment.workflow_task.current_assignee_content_type_id and assignment.workflow_task.current_assignee_content_type.model == "user" else None,
                    "workflow_task": _serialize_task_for_user(assignment.workflow_task, request.user),
                    "can_act": can_act,
                }
                if assignment
                else None
            ),
        }
        return Response(payload)

class AssignmentOptionsAPIView(APIView):
    def get(self, request):
        plant_id = request.query_params.get("plant_id")
        if not plant_id:
            return Response({"detail": "plant_id is required."}, status=status.HTTP_400_BAD_REQUEST)

        plant = get_object_or_404(_company_scope_plants(request.user), pk=plant_id)
        workflow_template = _resolve_brsr_workflow_template(request.user, plant)
        workflow_stage = _workflow_entry_stage(workflow_template) if workflow_template else None
        review_stage = _workflow_stage_by_type(workflow_template, "review") if workflow_template else None

        if workflow_stage and workflow_stage.role_id:
            assignees = _workflow_assignees_for_stage(plant, workflow_stage, current_user=request.user)
            try:
                default_assignee = _resolve_brsr_assignee(plant, workflow_template, current_user=request.user)
            except ValueError:
                default_assignee = None
            target_role_codes = [workflow_stage.role.role_code] if workflow_stage.role_id else []
        else:
            target_role_codes = []
            assignees = _plant_assignees(plant, current_user=request.user)
            default_assignee = _default_assignee_for_context(request.user, plant)

        if review_stage and review_stage.role_id:
            reviewers = _workflow_assignees_for_stage(plant, review_stage, current_user=request.user)
            try:
                default_reviewer = _resolve_brsr_reviewer(plant, workflow_template, current_user=request.user)
            except ValueError:
                default_reviewer = None
            reviewer_role_codes = [review_stage.role.role_code] if review_stage.role_id else []
        else:
            reviewers = User.objects.none()
            default_reviewer = None
            reviewer_role_codes = []

        return Response(
            {
                "plant": {"id": plant.id, "name": plant.name, "code": plant.code},
                "scope": _get_assignment_scope(request.user),
                "assignees": [_serialize_user(item) for item in assignees],
                "default_assignee": _serialize_user(default_assignee) if default_assignee else None,
                "reviewers": [_serialize_user(item) for item in reviewers],
                "default_reviewer": _serialize_user(default_reviewer) if default_reviewer else None,
                "target_role_codes": target_role_codes,
                "reviewer_role_codes": reviewer_role_codes,
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
        assignment = get_object_or_404(_assignment_queryset_for_user(request.user), pk=assignment_id)
        if not assignment.workflow_template_id:
            template = _resolve_brsr_workflow_template(request.user, assignment.plant)
            if template:
                assignment.workflow_template = template
                assignment.save(update_fields=["workflow_template", "updated_at"])
        from .views import _ensure_assignment_workflow_task
        _ensure_assignment_workflow_task(assignment, current_user=request.user)
        if assignment.workflow_task:
            task_info = _serialize_task_for_user(assignment.workflow_task, request.user)
            if not task_info.get("can_act", False):
                return Response(
                    {"detail": "You don't have permission to save this question."},
                    status=status.HTTP_403_FORBIDDEN,
                )
        stage_type = assignment.workflow_stage_type
        if stage_type and stage_type not in {"question_assignment", "data_entry"}:
            return Response(
                {"detail": "This question cannot be saved in the current workflow stage."},
                status=status.HTTP_409_CONFLICT,
            )
        response, _ = QuestionResponse.objects.get_or_create(
            assignment=assignment,
            question=question,
        )
        response.answered_by_content_type = ContentType.objects.get_for_model(User)
        response.answered_by_object_id = request.user.id
        if "response_value" in request.data:
            response.response_value = request.data.get("response_value") or ""
        if "response_json" in request.data:
            response.response_json = request.data.get("response_json") or {}
        response.save()
        if stage_type == "question_assignment":
            from .views import _advance_assignment_to_entry_stage
            _advance_assignment_to_entry_stage(assignment, actor=request.user)
        response.refresh_from_db()
        return Response(_serialize_question(question, assignment=assignment))


class QuestionSubmitAPIView(APIView):
    def post(self, request, question_id):
        question = get_object_or_404(_pdf_questions_queryset(), question_id=question_id)
        assignment_id = request.data.get("assignment_id")
        if not assignment_id:
            return Response(
                {"detail": "Create an assignment before submitting this response."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        assignment = get_object_or_404(_assignment_queryset_for_user(request.user), pk=assignment_id)
        if not assignment.workflow_template_id:
            template = _resolve_brsr_workflow_template(request.user, assignment.plant)
            if template:
                assignment.workflow_template = template
                assignment.save(update_fields=["workflow_template", "updated_at"])
        from .views import _ensure_assignment_workflow_task
        _ensure_assignment_workflow_task(assignment, current_user=request.user)
        response = get_object_or_404(QuestionResponse, assignment=assignment, question=question)
        if assignment.workflow_stage_type and assignment.workflow_stage_type != "data_entry":
            return Response(
                {"detail": "This question cannot be submitted in the current workflow stage."},
                status=status.HTTP_409_CONFLICT,
            )
        response.answered_by_content_type = ContentType.objects.get_for_model(User)
        response.answered_by_object_id = request.user.id
        task = assignment.workflow_task
        next_stage = task.current_stage.next_stage() if task and task.current_stage_id else None
        next_assignee = None
        if next_stage:
            try:
                next_assignee = _first_workflow_assignee_for_stage(
                    assignment.plant,
                    next_stage,
                    current_user=request.user,
                    assignment=assignment,
                )
            except ValueError as exc:
                return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        with transaction.atomic():
            response.submit(request.user)
            if next_stage and next_stage.stage_type == "review":
                WorkflowConfigurationEngine.advance_to_next_stage(
                    task,
                    request.user,
                    remark="Submitted for review.",
                    next_assignee=next_assignee,
                )
            else:
                WorkflowConfigurationEngine.approve(task, request.user, next_assignee=next_assignee)
            response.refresh_from_db()
        return Response(
            {
                "status": response.status,
                "workflow_task": _serialize_task_for_user(assignment.workflow_task, request.user),
            }
        )


class QuestionApproveAPIView(APIView):
    def post(self, request, question_id):
        question = get_object_or_404(_pdf_questions_queryset(), question_id=question_id)
        assignment_id = request.data.get("assignment_id")
        if not assignment_id:
            return Response({"detail": "Create an assignment before approving this response."}, status=status.HTTP_400_BAD_REQUEST)
        assignment = get_object_or_404(_assignment_queryset_for_user(request.user), pk=assignment_id)
        from .views import _ensure_assignment_workflow_task
        _ensure_assignment_workflow_task(assignment, current_user=request.user)
        response = get_object_or_404(QuestionResponse, assignment=assignment, question=question)
        task = assignment.workflow_task
        if not task:
            return Response({"detail": "No workflow task found for this response."}, status=status.HTTP_400_BAD_REQUEST)
        next_stage = task.current_stage.next_stage() if task.current_stage_id else None
        next_assignee = None
        if next_stage:
            try:
                next_assignee = _first_workflow_assignee_for_stage(
                    assignment.plant,
                    next_stage,
                    current_user=request.user,
                    assignment=assignment,
                )
            except ValueError as exc:
                return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        WorkflowConfigurationEngine.approve(task, request.user, next_assignee=next_assignee)
        response.refresh_from_db()
        return Response({"status": response.status, "workflow_task": _serialize_task_for_user(assignment.workflow_task, request.user)})


class QuestionRejectAPIView(APIView):
    def post(self, request, question_id):
        question = get_object_or_404(_pdf_questions_queryset(), question_id=question_id)
        assignment_id = request.data.get("assignment_id")
        remark = (request.data.get("remark") or "").strip()
        if not assignment_id:
            return Response({"detail": "Create an assignment before rejecting this response."}, status=status.HTTP_400_BAD_REQUEST)
        if not remark:
            return Response({"detail": "Rejection requires a remark."}, status=status.HTTP_400_BAD_REQUEST)
        assignment = get_object_or_404(_assignment_queryset_for_user(request.user), pk=assignment_id)
        from .views import _ensure_assignment_workflow_task
        _ensure_assignment_workflow_task(assignment, current_user=request.user)
        response = get_object_or_404(QuestionResponse, assignment=assignment, question=question)
        task = assignment.workflow_task
        if not task:
            return Response({"detail": "No workflow task found for this response."}, status=status.HTTP_400_BAD_REQUEST)
        return_to_stage = None
        if assignment.workflow_task and assignment.workflow_task.template_id:
            return_to_stage = assignment.workflow_task.template.stages.filter(stage_type="data_entry").first()
        return_to_assignee = getattr(response, "answered_by", None) or assignment.assignee
        WorkflowConfigurationEngine.reject(
            task,
            request.user,
            remark=remark,
            return_to_stage=return_to_stage,
            return_to_assignee=return_to_assignee,
        )
        response.refresh_from_db()
        return Response({"status": response.status, "workflow_task": _serialize_task_for_user(assignment.workflow_task, request.user)})


class QuestionReviewCommentAPIView(APIView):
    def post(self, request, question_id):
        question = get_object_or_404(_pdf_questions_queryset(), question_id=question_id)
        assignment_id = request.data.get("assignment_id")
        remark = (request.data.get("remark") or "").strip()
        if not assignment_id:
            return Response({"detail": "Create an assignment before saving a review comment."}, status=status.HTTP_400_BAD_REQUEST)

        assignment = get_object_or_404(_assignment_queryset_for_user(request.user), pk=assignment_id)
        from .views import _ensure_assignment_workflow_task
        _ensure_assignment_workflow_task(assignment, current_user=request.user)

        task = assignment.workflow_task
        if not task:
            return Response({"detail": "No workflow task found for this response."}, status=status.HTTP_400_BAD_REQUEST)
        if assignment.workflow_stage_type != "review":
            return Response({"detail": "Review comments can only be saved during the review stage."}, status=status.HTTP_409_CONFLICT)
        task_info = _serialize_task_for_user(task, request.user)
        if not task_info or not task_info.get("can_act", False):
            return Response({"detail": "You don't have permission to update this review comment."}, status=status.HTTP_403_FORBIDDEN)
        if not remark:
            return Response({"detail": "Reviewer comment is required before moving this stage forward."}, status=status.HTTP_400_BAD_REQUEST)

        response = get_object_or_404(QuestionResponse, assignment=assignment, question=question)
        response.review_remark = remark
        response.reviewed_by = request.user
        response.reviewed_at = timezone.now()
        next_stage = task.current_stage.next_stage() if task.current_stage_id else None
        next_assignee = None
        if next_stage:
            try:
                next_assignee = _first_workflow_assignee_for_stage(
                    assignment.plant,
                    next_stage,
                    current_user=request.user,
                    assignment=assignment,
                )
            except ValueError as exc:
                return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        with transaction.atomic():
            response.save(update_fields=["review_remark", "reviewed_by", "reviewed_at", "updated_at"])
            if next_stage:
                WorkflowConfigurationEngine.advance_to_next_stage(
                    task,
                    request.user,
                    remark=remark,
                    next_assignee=next_assignee,
                )
        response.refresh_from_db()
        return Response(
            {
                "status": response.status,
                "review_remark": response.review_remark or "",
                "workflow_task": _serialize_task_for_user(assignment.workflow_task, request.user),
            }
        )


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
            plant_queryset=_company_scope_plants(request.user),
            user_queryset=User.objects.filter(is_active=True).select_related("role", "department").order_by(
                "full_name", "username"
            ),
            question_queryset=questions,
            financial_year_queryset=FinancialYear.objects.all().order_by("-start_date"),
        )
        if not form.is_valid():
            return Response(form.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            assignment = _create_brsr_assignment(
                user=request.user,
                section=section,
                principle=principle,
                cleaned_data=form.cleaned_data,
                question_queryset=form.cleaned_data["question_ids"],
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        selected_questions = form.cleaned_data["question_ids"]
        return Response(
            {
                "id": assignment.id,
                "assignment_id": assignment.assignment_id,
                "question_count": selected_questions.count(),
            },
            status=status.HTTP_201_CREATED,
        )
