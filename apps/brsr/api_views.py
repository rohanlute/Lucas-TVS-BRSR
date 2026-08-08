import json
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from apps.organizations.models import FinancialYear, Plant
from apps.organizations.workflow_configuration_engine import WorkflowConfigurationEngine
from .forms import BRSRAssignmentForm, AssignmentScheduleForm
from .models import Assignment, BRSRPrinciple, BRSRQuestion, BRSRSection, QuestionResponse, WorkflowStatus, QuestionResponseDocument, AssignmentSchedule
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
    _assigned_reviewer_ids_for_assignment,
    _is_assigned_reviewer,
    _assignment_missing_responses,
    _next_non_review_stage,
)
from .services import create_assignment_and_optional_schedule


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
    
    status_display = "Final Approved & Locked" if (
        task and (
            task.is_completed
            or (task.current_stage and task.current_stage.stage_type in {"pre_final_approval", "final_approval"})
        )
    ) else ((response.status if response else "draft").replace("_", " ").title())
    
    documents = []
    if response:
        documents = [
            {
                "id": doc.id,
                "name": doc.original_name,
                "url": doc.document.url,
                "uploaded_at": doc.uploaded_at,
            }
            for doc in response.documents.all()
        ]
    
    # CRITICAL FIX: Get the actual response data from the database
    # Even if response is None, we need to return empty values
    response_value = response.response_value if response else ""
    response_json = response.response_json if response else {}
    review_remark = response.review_remark if response else ""
    is_editable = response.is_editable if response else True
    assignment_id = response.assignment.assignment_id if (response and response.assignment) else ""
    
    return {
        "question_id": question.question_id,
        "title": question.question_text,
        "question_number": question.question_number,
        "question_type": question.question_type,
        "status": response.status if response else "draft",
        "status_display": status_display,
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
        "_question_metadata": _question_metadata(question),
        # CRITICAL: These fields MUST be populated
        "response_value": response_value,  # This should be "Yes" for question 171
        "response_json": response_json,
        "review_remark": review_remark,
        "is_editable": is_editable,
        "assignment_id": assignment_id,
        "documents": documents,
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
    is_completed = bool(task.is_completed)
    stage_label = "Final Approved & Locked" if is_completed else (task.current_stage.label if task.current_stage_id else "")
    stage_type = "" if is_completed else (task.current_stage.stage_type if task.current_stage_id else "")
    assignee_id = task.current_assignee_object_id if task.current_assignee_content_type_id and task.current_assignee_content_type.model == "user" else None
    if is_completed:
        assignee_id = None
    current_user_role_id = getattr(user, "role_id", None)
    current_stage_role_id = task.current_stage.role_id if task.current_stage_id else None
    can_act = bool(
        user.is_authenticated
        and (
            user.is_superuser
            or getattr(user, "is_super_admin", False)
            or (current_user_role_id and current_stage_role_id and current_user_role_id == current_stage_role_id)
        )
    )
    if task.is_returned and assignee_id == getattr(user, "id", None):
        can_act = True
    if task.current_stage_id and task.current_stage.stage_type == "review":
        assignment = getattr(task.target, "assignment", None) or (task.target if isinstance(task.target, Assignment) else None)
        can_act = _is_assigned_reviewer(user, assignment)
    if is_completed:
        can_act = False
    return {
        "id": task.id,
        "stage": stage_label,
        "stage_type": stage_type,
        "stage_role_code": task.current_stage.role.role_code if task.current_stage_id and task.current_stage.role_id else "",
        "current_assignee_id": assignee_id,
        "current_assignee": "" if is_completed else (str(task.current_assignee) if task.current_assignee else ""),
        "can_act": can_act,
        "is_completed": is_completed,
        "status_label": "Final Approved & Locked" if is_completed else stage_label,
    }


def _parse_response_json_payload(raw_value):
    if raw_value in (None, ""):
        return {}
    if isinstance(raw_value, (dict, list)):
        return raw_value
    try:
        return json.loads(raw_value)
    except (TypeError, json.JSONDecodeError):
        return {}


def _completed_task_response():
    return Response(
        {"detail": "This workflow has already been completed."},
        status=status.HTTP_409_CONFLICT,
    )


def _ensure_assignment_task(assignment, user):
    if not assignment.workflow_template_id:
        template = _resolve_brsr_workflow_template(user, assignment.plant)
        if template:
            assignment.workflow_template = template
            assignment.save(update_fields=["workflow_template", "updated_at"])
    from .views import _ensure_assignment_workflow_task

    _ensure_assignment_workflow_task(assignment, current_user=user)
    return assignment.workflow_task


def _finalize_assignment_submission(assignment, user, *, force=False):
    task = _ensure_assignment_task(assignment, user)
    if task and task.is_completed:
        return None, _completed_task_response()
    if not assignment.is_editable and assignment.workflow_stage_type != "data_entry":
        return None, Response(
            {"detail": "This assignment cannot be submitted in the current workflow stage."},
            status=status.HTTP_409_CONFLICT,
        )

    missing_questions = _assignment_missing_responses(assignment)
    if missing_questions and not force:
        return None, Response(
            {
                "detail": "Some questions have not been filled yet.",
                "missing_questions": missing_questions,
                "requires_confirmation": True,
            },
            status=status.HTTP_409_CONFLICT,
        )

    questions = list(assignment.questions.select_related("section", "principle").order_by("display_order", "question_number"))
    responses = {
        response.question_id: response
        for response in assignment.responses.select_related("question")
    }
    with transaction.atomic():
        for question in questions:
            response = responses.get(question.id)
            if response is None and force:
                response = QuestionResponse.objects.create(
                    assignment=assignment,
                    question=question,
                    response_value="",
                    response_json={},
                )
                responses[question.id] = response
            if response is None:
                continue
            response.answered_by_content_type = ContentType.objects.get_for_model(User)
            response.answered_by_object_id = user.id
            response.status = WorkflowStatus.RESUBMITTED if response.resubmission_count else WorkflowStatus.SUBMITTED
            response.submitted_by = user
            response.submitted_at = timezone.now()
            response.save(update_fields=["status", "answered_by_content_type", "answered_by_object_id", "submitted_by", "submitted_at", "updated_at"])

        task = assignment.workflow_task
        if task:
            next_stage = task.current_stage.next_stage() if task.current_stage_id else None
            next_assignee = None
            if next_stage:
                if next_stage.stage_type == "review" and not assignment.reviewer_links.exists():
                    next_stage = _next_non_review_stage(next_stage)
                if next_stage:
                    try:
                        next_assignee = _first_workflow_assignee_for_stage(
                            assignment.plant,
                            next_stage,
                            current_user=user,
                            assignment=assignment,
                        )
                    except ValueError:
                        next_assignee = None
                        if next_stage.stage_type == "review":
                            next_stage = _next_non_review_stage(next_stage)
                            if next_stage:
                                try:
                                    next_assignee = _first_workflow_assignee_for_stage(
                                        assignment.plant,
                                        next_stage,
                                        current_user=user,
                                        assignment=assignment,
                                    )
                                except ValueError:
                                    next_assignee = None
            WorkflowConfigurationEngine.advance_to_next_stage(
                task,
                user,
                remark="Submitted for review.",
                next_assignee=next_assignee,
            )
    assignment.refresh_from_db()
    from .notifications import notify_assignment_submitted
    notify_assignment_submitted(assignment, next_assignee)
    return {
        "message": f"Assignment {assignment.assignment_id} submitted successfully.",
        "workflow_task": _serialize_task_for_user(assignment.workflow_task, user),
        "missing_questions": missing_questions,
    }, None


def _approve_assignment_stage(assignment, user):
    task = _ensure_assignment_task(assignment, user)
    if not task:
        return None, Response({"detail": "No workflow task found for this assignment."}, status=status.HTTP_400_BAD_REQUEST)
    if task.is_completed:
        return None, _completed_task_response()
    if assignment.workflow_stage_type == "review":
        if not _is_assigned_reviewer(user, assignment):
            return None, Response(
                {"detail": "Only the assigned reviewer can finalize the review stage."},
                status=status.HTTP_403_FORBIDDEN,
            )
        next_stage = task.current_stage.next_stage() if task.current_stage_id else None
        next_assignee = None
        if next_stage:
            try:
                next_assignee = _first_workflow_assignee_for_stage(
                    assignment.plant,
                    next_stage,
                    current_user=user,
                    assignment=assignment,
                )
            except ValueError:
                next_assignee = None
        WorkflowConfigurationEngine.advance_to_next_stage(
            task,
            user,
            remark="Reviewer comments finalized.",
            next_assignee=next_assignee,
        )
        assignment.refresh_from_db()
        return {
            "message": f"Assignment {assignment.assignment_id} review finalized successfully.",
            "workflow_task": _serialize_task_for_user(assignment.workflow_task, user),
        }, None
    if assignment.workflow_stage_type not in {"approval", "pre_final_approval", "final_approval"}:
        return None, Response(
            {"detail": "This assignment cannot be approved in the current workflow stage."},
            status=status.HTTP_409_CONFLICT,
        )
    next_stage = task.current_stage.next_stage() if task.current_stage_id else None
    next_assignee = None
    if next_stage:
        try:
            next_assignee = _first_workflow_assignee_for_stage(
                assignment.plant,
                next_stage,
                current_user=user,
                assignment=assignment,
            )
        except ValueError as exc:
            return None, Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    WorkflowConfigurationEngine.approve(task, user, next_assignee=next_assignee)
    assignment.refresh_from_db()
    if next_assignee and assignment.workflow_task and not assignment.workflow_task.is_completed:
        from .notifications import notify_assignment_submitted
        notify_assignment_submitted(assignment, next_assignee)
    if assignment.workflow_task and assignment.workflow_task.is_completed:
        from .notifications import notify_assignment_approved
        notify_assignment_approved(assignment)
    return {
        "message": f"Assignment {assignment.assignment_id} approved successfully.",
        "workflow_task": _serialize_task_for_user(assignment.workflow_task, user),
    }, None


def _reject_assignment_stage(assignment, user, remark):
    task = _ensure_assignment_task(assignment, user)
    if not task:
        return None, Response({"detail": "No workflow task found for this assignment."}, status=status.HTTP_400_BAD_REQUEST)
    if task.is_completed:
        return None, _completed_task_response()
    if assignment.workflow_stage_type == "review":
        return None, Response(
            {"detail": "Reviewer stage is comment-only. Please use the comment page instead."},
            status=status.HTTP_409_CONFLICT,
        )
    if assignment.workflow_stage_type not in {"approval", "pre_final_approval", "final_approval"}:
        return None, Response(
            {"detail": "This assignment cannot be rejected in the current workflow stage."},
            status=status.HTTP_409_CONFLICT,
        )
    if not remark:
        return None, Response({"detail": "Rejection requires a remark."}, status=status.HTTP_400_BAD_REQUEST)
    return_to_stage = None
    if task.template_id:
        return_to_stage = task.template.stages.filter(stage_type="data_entry").first()
    responses = list(assignment.responses.select_related("question"))
    WorkflowConfigurationEngine.reject(
        task,
        user,
        remark=remark,
        return_to_stage=return_to_stage,
        return_to_assignee=assignment.assignee,
    )
    for response in responses:
        if response.status in {WorkflowStatus.SUBMITTED, WorkflowStatus.RESUBMITTED}:
            response.status = WorkflowStatus.REJECTED
            response.reviewed_by = user
            response.reviewed_at = timezone.now()
            response.review_remark = remark
            response.save(update_fields=["status", "reviewed_by", "reviewed_at", "review_remark", "updated_at"])
    response_obj = _serialize_task_for_user(assignment.workflow_task, user)
    assignment.refresh_from_db()
    from .notifications import notify_assignment_rejected
    notify_assignment_rejected(assignment, remark)
    
    return {
        "message": f"Assignment {assignment.assignment_id} rejected and sent back for correction.",
        "workflow_task": response_obj,
    }, None


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
                .prefetch_related(
                    "questions", 
                    "questions__section", 
                    "questions__principle", 
                    "responses",  # CRITICAL: Prefetch responses
                    "responses__documents"  # Also prefetch documents
                )
                .filter(pk=assignment_id)
                .first()
            )
            
            # CRITICAL: Log what responses are found
            if assignment:
                response_count = assignment.responses.count()
                print(f"📝 Found {response_count} responses for assignment {assignment_id}")
                for resp in assignment.responses.all()[:5]:
                    print(f"   Question {resp.question_id}: value='{resp.response_value}', json={resp.response_json}")

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

        # Serialize questions - this will now include response data
        serialized_questions = [_serialize_question(question, assignment=assignment, user=request.user) for question in questions]
        
        # Log what's being returned
        for q in serialized_questions[:5]:
            print(f"📤 Question {q['question_number']}: response_value='{q.get('response_value', 'MISSING')}'")

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
            "topics": serialized_questions,  # This now includes response data
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
                    "workflow_stage": "Final Approved & Locked" if (assignment.workflow_task and (assignment.workflow_task.is_completed or (assignment.workflow_task.current_stage and assignment.workflow_task.current_stage.stage_type in {"pre_final_approval", "final_approval"}))) else assignment.workflow_stage_label,
                    "workflow_stage_type": "" if (assignment.workflow_task and assignment.workflow_task.is_completed) else workflow_stage_type,
                    "assignment_status": getattr(assignment, "assignment_status", "") or "",
                    "assignment_status_label": {
                        "pending": "Pending",
                        "in_progress": "In Progress",
                        "rejected": "Rejected",
                        "reassigned": "Reassigned",
                        "approved": "Approved",
                    }.get(getattr(assignment, "assignment_status", "") or "", (getattr(assignment, "assignment_status", "") or "").replace("_", " ").title()),
                    "workflow_status_label": {
                        "pending": "Pending",
                        "in_progress": "In Progress",
                        "rejected": "Rejected",
                        "reassigned": "Reassigned",
                        "approved": "Approved",
                    }.get(getattr(assignment, "assignment_status", "") or "", _serialize_task_for_user(assignment.workflow_task, request.user).get("status_label") if assignment.workflow_task else assignment.workflow_stage_label),
                    "current_assignee_id": None if (assignment.workflow_task and assignment.workflow_task.is_completed) else (assignment.workflow_task.current_assignee_object_id if assignment.workflow_task and assignment.workflow_task.current_assignee_content_type_id and assignment.workflow_task.current_assignee_content_type.model == "user" else None),
                    "workflow_task": _serialize_task_for_user(assignment.workflow_task, request.user),
                    "can_act": False if (assignment.workflow_task and assignment.workflow_task.is_completed) else can_act,
                    "is_editable": assignment.is_editable,
                    "assigned_reviewer_ids": _assigned_reviewer_ids_for_assignment(assignment),
                    "is_assigned_reviewer": _is_assigned_reviewer(request.user, assignment),
                    "is_completed": assignment.workflow_task.is_completed if assignment.workflow_task else False,
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
    parser_classes = (MultiPartParser, FormParser, JSONParser)
    
    def put(self, request, question_id):
        import logging
        logger = logging.getLogger(__name__)
        
        logger.info("=" * 50)
        logger.info("📝 QUESTION SAVE API CALLED")
        logger.info(f"Question ID: {question_id}")
        logger.info(f"User: {request.user}")
        
        # IMPORTANT: Log ALL data to see what's coming in
        logger.info(f"🔍 request.data: {request.data}")
        logger.info(f"🔍 request.POST: {request.POST}")
        logger.info(f"🔍 request.FILES: {request.FILES}")
        
        # If using FormData, data might be in request.POST or request.data
        assignment_id = request.data.get("assignment_id") or request.POST.get("assignment_id")
        response_value = request.data.get("response_value") or request.POST.get("response_value", "")
        response_json_raw = request.data.get("response_json") or request.POST.get("response_json", "{}")
        
        logger.info(f"Assignment ID: {assignment_id}")
        logger.info(f"Response value: {response_value[:50] if response_value else 'EMPTY'}")
        logger.info(f"Response JSON raw: {response_json_raw[:100] if response_json_raw else 'EMPTY'}")
        
        if not assignment_id:
            return Response(
                {"detail": "Assignment ID is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        
        # Get question
        try:
            question = get_object_or_404(_pdf_questions_queryset(), question_id=question_id)
            logger.info(f"✅ Question found: {question.question_id}")
        except Exception as e:
            logger.error(f"❌ Question not found: {str(e)}")
            return Response(
                {"detail": f"Question not found: {str(e)}"},
                status=status.HTTP_404_NOT_FOUND,
            )
        
        # Get assignment
        try:
            assignment = get_object_or_404(_assignment_queryset_for_user(request.user), pk=assignment_id)
            logger.info(f"✅ Assignment found: {assignment.id}")
        except Exception as e:
            logger.error(f"❌ Assignment not found: {str(e)}")
            return Response(
                {"detail": f"Assignment not found: {str(e)}"},
                status=status.HTTP_404_NOT_FOUND,
            )
        
        # Ensure workflow exists
        if not assignment.workflow_template_id:
            template = _resolve_brsr_workflow_template(request.user, assignment.plant)
            if template:
                assignment.workflow_template = template
                assignment.save(update_fields=["workflow_template", "updated_at"])
        
        from .views import _ensure_assignment_workflow_task
        _ensure_assignment_workflow_task(assignment, current_user=request.user)
        
        if assignment.workflow_task and assignment.workflow_task.is_completed:
            return Response(
                {"detail": "This workflow has already been completed."},
                status=status.HTTP_409_CONFLICT,
            )
        
        # Get or create response
        response, created = QuestionResponse.objects.get_or_create(
            assignment=assignment,
            question=question,
        )
        logger.info(f"Response {'created' if created else 'found'}: {response.id}")
        
        # Check permissions
        if assignment.workflow_task:
            task_info = _serialize_task_for_user(assignment.workflow_task, request.user)
            if not task_info.get("can_act", False):
                task = assignment.workflow_task
                assignee_is_current_user = bool(
                    task
                    and task.is_returned
                    and task.current_assignee_content_type_id
                    and task.current_assignee_content_type.model == "user"
                    and task.current_assignee_object_id == request.user.id
                )
                if not assignee_is_current_user:
                    return Response(
                        {"detail": "You don't have permission to save this question."},
                        status=status.HTTP_403_FORBIDDEN,
                    )
        
        if not assignment.is_editable and assignment.assignment_status not in {"rejected", "reassigned"}:
            return Response(
                {"detail": "This question cannot be saved in the current workflow stage."},
                status=status.HTTP_409_CONFLICT,
            )
        
        # Update response - CRITICAL: Always set the values even if empty
        response.answered_by_content_type = ContentType.objects.get_for_model(User)
        response.answered_by_object_id = request.user.id
        
        # Set response_value - IMPORTANT: Use the value from request
        logger.info(f"📝 Setting response_value to: {response_value}")
        response.response_value = response_value if response_value is not None else ""
        
        # Set response_json
        try:
            if response_json_raw:
                if isinstance(response_json_raw, str):
                    response.response_json = json.loads(response_json_raw) if response_json_raw else {}
                else:
                    response.response_json = response_json_raw
            else:
                response.response_json = {}
            logger.info(f"📝 Setting response_json to: {response.response_json}")
        except json.JSONDecodeError as e:
            logger.error(f"❌ JSON decode error: {e}")
            response.response_json = {}
        
        # Save the response
        try:
            response.save()
            logger.info(f"✅ Response {response.id} saved successfully")
            logger.info(f"   - response_value: {response.response_value[:50] if response.response_value else 'EMPTY'}")
            logger.info(f"   - response_json: {response.response_json}")
            logger.info(f"   - status: {response.status}")
        except Exception as e:
            logger.error(f"❌ Error saving response: {str(e)}")
            logger.error(f"❌ Traceback:", exc_info=True)
            return Response(
                {"detail": f"Error saving response: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        
        # Save uploaded files
        uploaded_files = request.FILES.getlist("documents")
        for uploaded_file in uploaded_files:
            QuestionResponseDocument.objects.create(
                response=response,
                document=uploaded_file,
                original_name=uploaded_file.name,
                uploaded_by=request.user,
            )
        
        # Advance workflow if needed
        if assignment.workflow_task and assignment.workflow_task.current_stage:
            stage_type = assignment.workflow_task.current_stage.stage_type
            if stage_type == "question_assignment":
                from .views import _advance_assignment_to_entry_stage
                _advance_assignment_to_entry_stage(assignment, actor=request.user)
        
        # Refresh from database
        response.refresh_from_db()
        
        # Get documents
        documents = [
            {
                "id": doc.id,
                "name": doc.original_name,
                "url": doc.document.url,
                "uploaded_at": doc.uploaded_at,
            }
            for doc in response.documents.all()
        ]
        
        logger.info("=" * 50)
        
        return Response({
            "status": "success",
            "message": f"Draft saved for question {question.question_number}.",
            "response_value": response.response_value,
            "response_json": response.response_json,
            "status": response.status,
            "id": response.id,
            "question_id": question.question_id,
            "documents": documents,
        })

class QuestionSubmitAPIView(APIView):
    def post(self, request, question_id):
        question = get_object_or_404(_pdf_questions_queryset(), question_id=question_id)
        assignment_id = request.data.get("assignment_id")
        force = str(request.data.get("force", "")).lower() in {"1", "true", "yes", "on"}
        if not assignment_id:
            return Response(
                {"detail": "Create an assignment before submitting this response."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        assignment = get_object_or_404(_assignment_queryset_for_user(request.user), pk=assignment_id)
        _ensure_assignment_task(assignment, request.user)
        result, error_response = _finalize_assignment_submission(assignment, request.user, force=force)
        if error_response:
            return error_response
        return Response(
            {
                "status": "submitted",
                "workflow_task": result["workflow_task"],
                "missing_questions": result["missing_questions"],
                "message": result["message"],
            }
        )


class QuestionApproveAPIView(APIView):
    def post(self, request, question_id):
        assignment_id = request.data.get("assignment_id")
        if not assignment_id:
            return Response(
                {"detail": "Create an assignment before approving this response."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        assignment = get_object_or_404(
            _assignment_queryset_for_user(request.user),
            pk=assignment_id,
        )

        result, error_response = _approve_assignment_stage(assignment, request.user)
        if error_response:
            return error_response
        return Response(
            {
                "status": "approved",
                "workflow_task": result["workflow_task"],
                "message": result["message"],
                "redirect_url": reverse("brsr:approval_dashboard"),
            }
        )


class QuestionRejectAPIView(APIView):
    def post(self, request, question_id):
        assignment_id = request.data.get("assignment_id")
        remark = (request.data.get("remark") or "").strip()
        if not assignment_id:
            return Response({"detail": "Create an assignment before rejecting this response."}, status=status.HTTP_400_BAD_REQUEST)
        assignment = get_object_or_404(_assignment_queryset_for_user(request.user), pk=assignment_id)
        result, error_response = _reject_assignment_stage(assignment, request.user, remark)
        if error_response:
            return error_response
        return Response(
            {
                "status": "rejected",
                "workflow_task": result["workflow_task"],
                "message": result["message"],
            }
        )


class QuestionReviewCommentAPIView(APIView):
    def post(self, request, question_id):
        question = get_object_or_404(_pdf_questions_queryset(), question_id=question_id)
        assignment_id = request.data.get("assignment_id")
        remark = (request.data.get("remark") or "").strip()
        
        if not assignment_id:
            return Response(
                {"detail": "Create an assignment before saving a review comment."},
                status=status.HTTP_400_BAD_REQUEST
            )

        assignment = get_object_or_404(
            _assignment_queryset_for_user(request.user), 
            pk=assignment_id
        )
        
        from .views import _ensure_assignment_workflow_task
        _ensure_assignment_workflow_task(assignment, current_user=request.user)

        task = assignment.workflow_task
        if not task:
            return Response(
                {"detail": "No workflow task found for this response."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if task.is_completed:
            return _completed_task_response()

        # Check if current stage is review
        if task.current_stage.stage_type != "review":
            return Response(
                {"detail": f"Comments can only be added during the Review stage. Current stage: {task.current_stage.stage_type}"},
                status=status.HTTP_409_CONFLICT,
            )

        # Check if user is the assigned reviewer
        if not _is_assigned_reviewer(request.user, assignment):
            return Response(
                {"detail": "Only the assigned reviewer can add comments."},
                status=status.HTTP_403_FORBIDDEN,
            )
            
        # Save or clear the comment. Reviewer notes are optional.
        response = get_object_or_404(
            QuestionResponse, 
            assignment=assignment, 
            question=question
        )
        response.review_remark = remark
        response.reviewed_by = request.user
        response.reviewed_at = timezone.now()
        response.save(update_fields=["review_remark", "reviewed_by", "reviewed_at", "updated_at"])
        response.refresh_from_db()

        return Response({
            "status": "saved",
            "review_remark": response.review_remark or "",
            "workflow_task": _serialize_task_for_user(assignment.workflow_task, request.user),
            "message": "Review comment saved successfully.",
            "should_redirect": False,
        })


class AssignmentFinalizeReviewAPIView(APIView):
    def post(self, request, assignment_id):
        assignment = get_object_or_404(
            _assignment_queryset_for_user(request.user),
            pk=assignment_id,
        )

        task = _ensure_assignment_task(assignment, request.user)
        if not task:
            return Response({"detail": "No workflow task found for this assignment."}, status=status.HTTP_400_BAD_REQUEST)
        if task.is_completed:
            return _completed_task_response()
        if task.current_stage.stage_type != "review":
            return Response(
                {"detail": "This assignment can only be finalized from the review stage."},
                status=status.HTTP_409_CONFLICT,
            )
        if not _is_assigned_reviewer(request.user, assignment):
            return Response(
                {"detail": "Only the assigned reviewer can finalize the review stage."},
                status=status.HTTP_403_FORBIDDEN,
            )

        from .views import _first_workflow_assignee_for_stage, _next_non_review_stage
        from django.urls import reverse

        next_stage = task.current_stage.next_stage() if task.current_stage_id else None
        while next_stage and next_stage.stage_type == "review":
            next_stage = _next_non_review_stage(next_stage)

        next_assignee = None
        if next_stage:
            try:
                next_assignee = _first_workflow_assignee_for_stage(
                    assignment.plant,
                    next_stage,
                    current_user=request.user,
                    assignment=assignment,
                )
            except ValueError:
                next_assignee = None

        WorkflowConfigurationEngine.advance_to_next_stage(
            task,
            request.user,
            remark="Review finalized.",
            next_assignee=next_assignee,
        )

        assignment.assignment_status = "in_progress"
        assignment.save(update_fields=["assignment_status", "updated_at"])
        assignment.refresh_from_db()

        if next_assignee:
            from .notifications import notify_assignment_submitted
            notify_assignment_submitted(assignment, next_assignee)

        redirect_url = reverse("brsr:approval_dashboard")
        return Response(
            {
                "status": "finalized",
                "workflow_task": _serialize_task_for_user(assignment.workflow_task, request.user),
                "message": "Review finalized successfully.",
                "redirect_url": redirect_url,
                "should_redirect": True,
                "next_stage": next_stage.label if next_stage else "Completed",
            }
        )


class AssignmentApproveAPIView(APIView):
    def post(self, request, assignment_id):
        assignment = get_object_or_404(
            _assignment_queryset_for_user(request.user),
            pk=assignment_id,
        )

        result, error_response = _approve_assignment_stage(assignment, request.user)
        if error_response:
            return error_response

        return Response(
            {
                "status": "approved",
                "workflow_task": result["workflow_task"],
                "message": result["message"],
                "redirect_url": reverse("brsr:approval_dashboard"),
            }
        )


class AssignmentRejectAPIView(APIView):
    def post(self, request, assignment_id):
        remark = (request.data.get("remark") or "").strip()
        assignment = get_object_or_404(_assignment_queryset_for_user(request.user), pk=assignment_id)
        result, error_response = _reject_assignment_stage(assignment, request.user, remark)
        if error_response:
            return error_response
        return Response(
            {
                "status": "rejected",
                "workflow_task": result["workflow_task"],
                "message": result["message"],
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

        # Get the reviewer from request data before creating the form
        reviewer_id = request.data.get("reviewer")
        reviewer = None
        if reviewer_id:
            try:
                reviewer = User.objects.get(id=reviewer_id)
            except User.DoesNotExist:
                return Response(
                    {"detail": f"Reviewer with ID {reviewer_id} not found."},
                    status=status.HTTP_400_BAD_REQUEST
                )

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
        if reviewer:
            form.cleaned_data['reviewer'] = reviewer

        try:
            assignment, schedule = create_assignment_and_optional_schedule(
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
                "reviewer_saved": bool(assignment.reviewer_links.exists()),
                "schedule_id": schedule.schedule_id if schedule else None,
                "message": f"Assignment {assignment.assignment_id} created successfully.",
            },
            status=status.HTTP_201_CREATED,
        )


class AssignmentScheduleCreateAPIView(APIView):
    """
    Creates a reusable AssignmentSchedule plus the immediate current-period
    Assignment using the same combined service path used by the regular
    assignment creation flow. This preserves the original assignee/reviewer
    and other metadata on the schedule, while also generating the first
    manual-style assignment for the current period and keeping the schedule
    active for future recurring generation.
    """
 
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
 
        form = AssignmentScheduleForm(
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
 
        selected_questions = form.cleaned_data["question_ids"]
        if not selected_questions.exists():
            return Response({"detail": "Select at least one question for the schedule."}, status=status.HTTP_400_BAD_REQUEST)
 
        assignee_id = request.data.get("assignee")
        assignee = None
        if assignee_id:
            try:
                assignee = User.objects.get(id=assignee_id)
            except User.DoesNotExist:
                return Response({"detail": f"Assignee with ID {assignee_id} not found."}, status=status.HTTP_400_BAD_REQUEST)
 
        reviewer_id = request.data.get("reviewer")
        reviewer = None
        if reviewer_id:
            try:
                reviewer = User.objects.get(id=reviewer_id)
            except User.DoesNotExist:
                return Response({"detail": f"Reviewer with ID {reviewer_id} not found."}, status=status.HTTP_400_BAD_REQUEST)
 
        cleaned_data = {
            "plant": form.cleaned_data["plant"],
            "financial_year": form.cleaned_data["financial_year"],
            "assignee": assignee,
            "reviewer": reviewer,
            "priority": form.cleaned_data["priority"],
            "notes": form.cleaned_data.get("notes"),
            "due_date": None,
            "data_collection_frequency": form.cleaned_data["frequency"],
            "weekly_start_day": form.cleaned_data.get("weekly_start_day"),
            "weekly_end_day": form.cleaned_data.get("weekly_end_day"),
            "selected_months": form.cleaned_data.get("selected_months") or [],
            "selected_quarters": form.cleaned_data.get("selected_quarters") or [],
            "assigner": request.user,
            "schedule_name": form.cleaned_data.get("name") or f"{section.name} recurring assignment",
        }
 
        try:
            assignment, schedule = create_assignment_and_optional_schedule(
                user=request.user,
                section=section,
                principle=principle,
                cleaned_data=cleaned_data,
                question_queryset=selected_questions,
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
 
        return Response(
            {
                "id": assignment.id,
                "assignment_id": assignment.assignment_id,
                "schedule_id": schedule.schedule_id,
                "question_count": selected_questions.count(),
                "is_recurring": True,
                "message": (
                    f"Assignment {assignment.assignment_id} created successfully. "
                    f"Recurring schedule {schedule.schedule_id} set up — future "
                    f"periods will be generated automatically with the same "
                    f"assignee, reviewer and settings."
                ),
            },
            status=status.HTTP_201_CREATED,
        )
 
 
class AssignmentScheduleListAPIView(APIView):
    """Lists schedules in scope for the current user's company/plants, with
    a running count of how many Assignments each one has generated so far
    — useful for an admin management screen."""
 
    def get(self, request):
        plant_id = request.query_params.get("plant_id")
        queryset = AssignmentSchedule.objects.select_related("plant", "section", "principle").filter(
            plant__in=_company_scope_plants(request.user)
        ).order_by("-created_at")
        if plant_id:
            queryset = queryset.filter(plant_id=plant_id)
 
        data = [
            {
                "id": item.id,
                "schedule_id": item.schedule_id,
                "name": item.name,
                "plant": item.plant.name,
                "section": item.section.name,
                "principle": item.principle.principle_name if item.principle_id else "",
                "frequency": item.get_frequency_display(),
                "financial_year": item.financial_year,
                "is_active": item.is_active,
                "question_count": item.questions.count(),
                "generated_count": item.generated_assignments.count(),
            }
            for item in queryset
        ]
        return Response({"schedules": data})
 
 
class AssignmentScheduleToggleAPIView(APIView):
    """Activates/deactivates a schedule. An inactive schedule is simply
    skipped by the daily generation task — no assignments are ever
    retroactively removed."""
 
    def post(self, request, schedule_id):
        schedule = get_object_or_404(
            AssignmentSchedule, pk=schedule_id, plant__in=_company_scope_plants(request.user)
        )
        schedule.is_active = not schedule.is_active
        schedule.save(update_fields=["is_active", "updated_at"])
        return Response({"id": schedule.id, "is_active": schedule.is_active})
