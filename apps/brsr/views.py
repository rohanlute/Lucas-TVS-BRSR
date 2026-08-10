import json
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.generic import TemplateView
from urllib.parse import urlencode
from apps.accounts.models import Department
from apps.accounts.models.permission import Permissions
from apps.companies.models import Company
from apps.organizations.models import ApprovalConfigurationTemplate, ApprovalConfigurationTask, FinancialYear, Plant
from apps.organizations.workflow_configuration_engine import WorkflowConfigurationEngine
from .forms import BRSRAssignmentForm, AssignmentScheduleForm
from .models import *
from django.db.models import Case, When, Value, IntegerField
from django.core.exceptions import PermissionDenied
from django.utils.html import escape
from datetime import date
from django.utils import timezone
from .services import create_assignment_and_optional_schedule


User = get_user_model()

def _section_scope_queryset():
    return (
        BRSRSection.objects.filter(is_active=True)
        .order_by("display_order", "code")
        .prefetch_related("questions")
    )

def _principle_queryset():
    return (
        BRSRPrinciple.objects.filter(is_active=True)
        .order_by("principle_number")
        .prefetch_related("questions")
    )


def _pdf_questions_queryset():
    return BRSRQuestion.objects.filter(is_active=True)


def _get_default_section():
    return BRSRSection.objects.filter(is_active=True).order_by("display_order", "code").first()


def _get_default_principle():
    return BRSRPrinciple.objects.filter(is_active=True).order_by("principle_number").first()


def _workflow_template_queryset():
    return (
        ApprovalConfigurationTemplate.objects.filter(is_active=True, framework="BRSR")
        .select_related("company")
        .prefetch_related("stages", "stages__role", "stages__escalation_role")
        .order_by("company__company_name", "name")
    )


def _workflow_stage_by_type(template, stage_type):
    if not template or not stage_type:
        return None
    return template.stages.filter(stage_type=stage_type).order_by("level").first()


def _workflow_entry_stage(template):
    if not template:
        return None

    first_stage = template.first_stage
    if not first_stage:
        return None

    if first_stage.stage_type == "question_assignment":
        next_stage = first_stage.next_stage()
        if next_stage:
            return next_stage

    return first_stage


def _company_scope_plants(user):
    queryset = Plant.objects.filter(is_active=True)
    if user.is_superuser or getattr(user, "is_super_admin", False):
        return queryset.order_by("name")
    if getattr(user, "company_id", None):
        return queryset.filter(created_by__company_id=user.company_id).order_by("name")
    return queryset.filter(id__in=user.assigned_plants.filter(is_active=True).values_list("id", flat=True)).order_by("name")


def _assignment_queryset_for_user(user):
    """Return assignments the user has access to."""
    queryset = Assignment.objects.all()
    
    if user.is_superuser or getattr(user, "is_super_admin", False):
        return queryset
    
    # Check if user has a company
    if getattr(user, "company_id", None):
        return queryset.filter(plant__created_by__company_id=user.company_id)
    
    # For regular users, filter by assigned plants
    plant_ids = user.assigned_plants.filter(is_active=True).values_list("id", flat=True)
    return queryset.filter(plant_id__in=plant_ids)


def _resolve_brsr_workflow_template(user=None, plant=None):
    queryset = _workflow_template_queryset()

    company_id = getattr(user, "company_id", None)
    if company_id:
        template = queryset.filter(company_id=company_id).first()
        if template:
            return template

    plant_company_id = getattr(getattr(plant, "created_by", None), "company_id", None)
    if plant_company_id:
        template = queryset.filter(company_id=plant_company_id).first()
        if template:
            return template

    return queryset.first()


def _workflow_assignees_for_stage(plant, stage, current_user=None):
    if not plant:
        return User.objects.none()

    if not stage or not stage.role_id:
        return _plant_assignees(plant, current_user=current_user)

    queryset = (
        User.objects.filter(
            is_active=True,
            assigned_plants=plant,
            role_id=stage.role_id,
        )
        .select_related("role", "department")
        .order_by("full_name", "username")
    )
    plant_company_id = getattr(getattr(plant, "created_by", None), "company_id", None)
    if plant_company_id:
        queryset = queryset.filter(company_id=plant_company_id)
    if current_user:
        queryset = queryset.exclude(pk=current_user.pk)
    queryset = queryset.distinct()
    if queryset.exists() or not stage or not stage.role_id:
        return queryset

    fallback = (
        User.objects.filter(
            is_active=True,
            role_id=stage.role_id,
        )
        .select_related("role", "department")
        .order_by("full_name", "username")
    )
    if plant_company_id:
        fallback = fallback.filter(company_id=plant_company_id)
    if current_user:
        fallback = fallback.exclude(pk=current_user.pk)
    fallback = fallback.distinct()
    if fallback.exists() or not stage or stage.stage_type != "review":
        return fallback

    company_users = (
        User.objects.filter(
            is_active=True,
            company_id=plant_company_id,
        )
        .select_related("role", "department")
        .order_by("full_name", "username")
    )
    if current_user:
        company_users = company_users.exclude(pk=current_user.pk)
    return company_users.distinct()


def _approval_bundle_assignments(user, company_id, section_code, financial_year, principle_slug=None, stage_type=None):
    queryset = _assignment_queryset_for_user(user).select_related(
        "plant",
        "section",
        "principle",
        "workflow_template",
        "assignee_content_type",
        "assigner_content_type",
    ).prefetch_related(
        "questions",
        "questions__section",
        "questions__principle",
        "responses",
        "responses__question",
    )
    if company_id:
        queryset = queryset.filter(plant__created_by__company_id=company_id)
    if section_code:
        queryset = queryset.filter(section__code=section_code)
    if financial_year:
        queryset = queryset.filter(financial_year=financial_year)
    if principle_slug is not None:
        if principle_slug:
            queryset = queryset.filter(principle__slug=principle_slug)
        else:
            queryset = queryset.filter(principle__isnull=True)

    assignments = list(queryset)
    if stage_type:
        assignments = [assignment for assignment in assignments if assignment.workflow_stage_type == stage_type]
    return assignments


def _serialize_consolidated_bundle_question(question, response=None, assignment=None, user=None):
    rendered_html = ""
    if question:
        rendered_html = _render_question_readonly_html(question, response)
    documents = []
    if response:
        documents = [
            {
                "id": doc.id,
                "name": doc.original_name,
                "url": doc.document.url,
            }
            for doc in response.documents.all()
        ]
    return {
        "question_id": question.question_id if question else "",
        "title": question.question_text if question else "",
        "number": question.question_number if question else "",
        "question_type": question.question_type if question else "",
        "status": response.status if response else "draft",
        "status_display": "Final Approved & Locked" if (assignment and assignment.workflow_task and (assignment.workflow_task.is_completed or (assignment.workflow_task.current_stage and assignment.workflow_task.current_stage.stage_type in {"pre_final_approval", "final_approval"}))) else ((response.status if response else "draft").replace("_", " ").title()),
        "workflow_stage": "Final Approved & Locked" if (assignment and assignment.workflow_task and assignment.workflow_task.is_completed) else (assignment.workflow_stage_label if assignment else ""),
        "workflow_stage_type": "" if (assignment and assignment.workflow_task and assignment.workflow_task.is_completed) else (assignment.workflow_stage_type if assignment else ""),
        "response_value": response.response_value if response else "",
        "response_json": response.response_json if response else {},
        "review_remark": response.review_remark if response else "",
        "documents": documents,
        "rendered_html": rendered_html,
    }


def _reviewer_links_for_assignment(assignment):
    if not assignment:
        return []
    return [link.reviewer for link in assignment.reviewer_links.select_related("reviewer_content_type").all() if link.reviewer]


def _assigned_reviewer_ids_for_assignment(assignment):
    if not assignment:
        return []
    return [link.reviewer_object_id for link in assignment.reviewer_links.all() if link.reviewer_object_id]


def _is_assigned_reviewer(user, assignment):
    if not user or not getattr(user, "is_authenticated", False) or not assignment:
        return False
    return user.id in _assigned_reviewer_ids_for_assignment(assignment)


def _first_workflow_assignee_for_stage(plant, stage, current_user=None, assignment=None):
    if assignment and stage and stage.stage_type == "review":
        assigned_reviewers = _reviewer_links_for_assignment(assignment)
        eligible_reviewers = _workflow_assignees_for_stage(plant, stage, current_user=current_user)
        for reviewer in assigned_reviewers:
            if reviewer and eligible_reviewers.filter(pk=reviewer.pk).exists():
                return reviewer

    assignee = _workflow_assignees_for_stage(plant, stage, current_user=current_user).first()
    if stage and stage.role_id and assignee is None:
        raise ValueError(f"No eligible assignee found for stage '{stage.label}'.")
    return assignee


def _resolve_brsr_assignee(plant, template, selected_assignee=None, current_user=None):
    stage = _workflow_entry_stage(template) if template else None
    if not stage or not stage.role_id:
        return selected_assignee or _workflow_assignees_for_stage(plant, stage, current_user=current_user).first()

    eligible = _workflow_assignees_for_stage(plant, stage, current_user=current_user)
    if selected_assignee and eligible.filter(pk=selected_assignee.pk).exists():
        return selected_assignee

    default_assignee = eligible.first()
    if default_assignee:
        return default_assignee

    raise ValueError("No eligible assignee matches the first stage of the configured BRSR workflow.")


def _resolve_brsr_reviewer(plant, template, selected_reviewer=None, current_user=None):
    review_stage = _workflow_stage_by_type(template, "review")
    if not review_stage or not review_stage.role_id:
        return selected_reviewer

    eligible = _workflow_assignees_for_stage(plant, review_stage, current_user=current_user)
    if selected_reviewer and eligible.filter(pk=selected_reviewer.pk).exists():
        return selected_reviewer

    return None


def _next_non_review_stage(stage):
    next_stage = stage.next_stage() if stage else None
    while next_stage and next_stage.stage_type == "review":
        next_stage = next_stage.next_stage()
    return next_stage


def _advance_assignment_to_entry_stage(assignment, actor=None):
    """
    If the workflow starts with a question-assignment gate, move it forward to
    the actual data-entry stage so the assignee can work on the response.
    """
    task = assignment.workflow_task
    if not task or not task.current_stage_id:
        return task

    current_stage = task.current_stage
    if not current_stage or current_stage.stage_type != "question_assignment":
        return task

    next_stage = current_stage.next_stage()
    if not next_stage:
        return task

    if next_stage.stage_type != "data_entry":
        return task

    assignee_role_id = getattr(getattr(assignment, "assignee", None), "role_id", None)
    if next_stage.role_id and assignee_role_id != next_stage.role_id:
        return task

    WorkflowConfigurationEngine.advance_to_next_stage(
        task,
        assignment.assigner or actor or assignment.assignee,
        remark="Auto-advanced to data entry stage after assignment creation.",
        next_assignee=assignment.assignee,
    )
    return task


def _is_approval_stage(stage_type):
    return stage_type in {"review", "approval", "pre_final_approval", "final_approval"}


def _is_admin_scope(user):
    role_code = getattr(getattr(user, "role", None), "role_code", "") or ""
    return bool(user.is_superuser or getattr(user, "is_super_admin", False) or role_code == "COMPANYADMIN")


def _my_assignment_ids(user):
    """Assignment IDs where THIS user personally is the assignee or an
    assigned reviewer — not the plant, not the department, not 'anyone
    with this role'."""
    user_ct = ContentType.objects.get_for_model(User)
    ids = set(
        Assignment.objects.filter(
            assignee_content_type=user_ct, assignee_object_id=user.id
        ).values_list("id", flat=True)
    )
    ids |= set(
        Assignment.objects.filter(
            reviewer_links__reviewer_content_type=user_ct,
            reviewer_links__reviewer_object_id=user.id,
        ).values_list("id", flat=True)
    )
    return ids


def _my_dashboard_assignment_queryset(user):
    """
    Strict per-user dashboard scope.
    Admin/company-admin roles keep full company visibility (they need it
    to manage things). Every other role — ESG coordinator, plant
    coordinator, department user/approver, reviewer, approver — only
    sees assignments where they are personally the assignee, the
    assigned reviewer, or the current workflow-task assignee (covers
    approval / pre-final / final-approval hand-offs to a specific person).
    """
    base = _assignment_queryset_for_user(user)
    if _is_admin_scope(user):
        return base

    my_ids = _my_assignment_ids(user)

    user_ct = ContentType.objects.get_for_model(User)
    assignment_ct = ContentType.objects.get_for_model(Assignment)
    task_assignment_ids = set(
        ApprovalConfigurationTask.objects.filter(
            target_content_type=assignment_ct,
            current_assignee_content_type=user_ct,
            current_assignee_object_id=user.id,
        ).values_list("target_object_id", flat=True)
    )

    role_task_assignment_ids = set()
    role_id = getattr(user, "role_id", None)
    if role_id:
        role_task_assignment_ids = set(
            ApprovalConfigurationTask.objects.filter(
                target_content_type=assignment_ct,
                current_stage__stage_type__in={"approval", "pre_final_approval", "final_approval"},
                current_stage__role_id=role_id,
            ).values_list("target_object_id", flat=True)
        )

    return base.filter(id__in=(my_ids | task_assignment_ids | role_task_assignment_ids))


def _plant_scope_assignment_queryset(user, plant):
    """
    Business-rule scope: ALL assignments for a plant (within the user's
    company/plant access), regardless of who owns each one. Used for
    integrity checks — section locking, pre-final readiness — which must
    consider every assignment in the plant/section/FY, not just the
    current user's own slice. Never use this for dashboard display.
    """
    return _assignment_queryset_for_user(user).filter(plant=plant)


def _can_user_act_on_assignment(user, assignment, strict_user_only=True):
    if not assignment:
        return False

    _ensure_assignment_workflow_task(assignment, current_user=user)
    task = assignment.workflow_task
    if not task:
        return False

    if strict_user_only and not _is_admin_scope(user):
        stage = task.current_stage if task.current_stage_id else None
        if not stage:
            return False

        assignee_id = task.current_assignee_object_id if (
            task.current_assignee_content_type_id
            and task.current_assignee_content_type.model == "user"
        ) else None

        if stage.stage_type == "review":
            return _is_assigned_reviewer(user, assignment)

        if stage.stage_type in {"approval", "pre_final_approval", "final_approval"}:
            if not stage.role_id:
                return False
            return bool(getattr(user, "role_id", None) == stage.role_id)

        return bool(assignee_id == user.id)

    task_info = _serialize_task_for_user(task, user)
    return bool(task_info and task_info.get("can_act"))


def _approval_stage_queryset(user):
    assignments = _my_dashboard_assignment_queryset(user).select_related(
        "plant",
        "section",
        "principle",
        "workflow_template",
        "assignee_content_type",
        "assigner_content_type",
    ).prefetch_related(
        "questions",
        "responses",
        "questions__section",
        "questions__principle",
    )
    actionable = []
    for assignment in assignments:
        if assignment.workflow_stage_type and _is_approval_stage(assignment.workflow_stage_type):
            if _can_user_act_on_assignment(user, assignment):
                actionable.append(assignment)
    return actionable


def _build_brsr_selection_filters(user, request):
    plants = list(_company_scope_plants(user)) if _is_admin_scope(user) else list(user.assigned_plants.filter(is_active=True).order_by("name"))
    selected_plant = None
    selected_plant_id = request.GET.get("plant", "")
    if selected_plant_id:
        selected_plant = next((plant for plant in plants if str(plant.id) == str(selected_plant_id)), None)
    if not selected_plant and plants:
        selected_plant = plants[0]

    financial_years = list(
        Assignment.objects.filter(plant__in=plants)
        .order_by("-financial_year")
        .values_list("financial_year", flat=True)
        .distinct()
    )
    selected_financial_year = request.GET.get("financial_year", "")
    if selected_financial_year and selected_financial_year not in financial_years:
        selected_financial_year = ""
    if not selected_financial_year and financial_years:
        selected_financial_year = financial_years[0]

    return {
        "plants": plants,
        "selected_plant": selected_plant,
        "selected_plant_id": getattr(selected_plant, "id", None),
        "financial_years": financial_years,
        "selected_financial_year": selected_financial_year,
    }


def _is_assignment_ready_for_pre_final(assignment):
    task = assignment.workflow_task
    if not task:
        return False
    if task.is_completed:
        return False
    current_stage = task.current_stage
    return bool(
        current_stage
        and current_stage.stage_type == "approval"
        and assignment.overall_status == "completed"
    )


def _section_principle_assignments_for_pre_final(user, plant, section, principle, financial_year):
    if not plant or not section or not financial_year:
        return []

    assignments = list(
        _plant_scope_assignment_queryset(user, plant)
        .filter(
            section_id=section.id,
            financial_year=financial_year,
        )
        .select_related("plant", "section", "principle", "workflow_template")
    )
    if principle:
        assignments = [assignment for assignment in assignments if assignment.principle_id == principle.id]
    else:
        assignments = [assignment for assignment in assignments if assignment.principle_id is None]
    return assignments


def _section_principle_ready_for_pre_final(user, plant, section, principle, financial_year):
    assignments = _section_principle_assignments_for_pre_final(user, plant, section, principle, financial_year)
    if not assignments:
        return False, 0

    for assignment in assignments:
        _ensure_assignment_workflow_task(assignment, current_user=user)
        if not _is_assignment_ready_for_pre_final(assignment):
            return False, len(assignments)
    return True, len(assignments)


def _serialize_workflow_task(task):
    if not task:
        return None
    is_completed = bool(task.is_completed)
    stage_label = "Final Approved & Locked" if is_completed else (task.current_stage.label if task.current_stage_id else "")
    stage_type = "" if is_completed else (task.current_stage.stage_type if task.current_stage_id else "")
    return {
        "id": task.id,
        "template": task.template.name if task.template_id else "",
        "stage": stage_label,
        "stage_type": stage_type,
        "stage_level": task.current_stage.level if task.current_stage_id else None,
        "assignee": "" if is_completed else (str(task.current_assignee) if task.current_assignee else ""),
        "is_completed": task.is_completed,
        "is_returned": task.is_returned,
        "is_overdue": task.is_overdue,
        "history_url": reverse("organizations:workflow_configuration_task_history", kwargs={"pk": task.pk}),
    }


def _ensure_assignment_workflow_task(assignment, current_user=None):
    if assignment.workflow_task:
        task = assignment.workflow_task
        _advance_assignment_to_entry_stage(assignment, actor=current_user)
        return task
    template = assignment.workflow_template
    if not template:
        template = _resolve_brsr_workflow_template(user=current_user, plant=assignment.plant)
        if template:
            assignment.workflow_template = template
            assignment.save(update_fields=["workflow_template", "updated_at"])
    if not template or not template.first_stage:
        return None
    first_assignee = assignment.assignee or current_user
    if first_assignee is None:
        return None
    task = WorkflowConfigurationEngine.start(template, assignment, first_assignee)
    _advance_assignment_to_entry_stage(assignment, actor=current_user)
    return task


def _get_section_principle(section_code=None, principle_slug=None):
    section = None
    principle = None

    if section_code:
        section = get_object_or_404(BRSRSection, code=section_code, is_active=True)
    else:
        section = _get_default_section()

    if section and section.code == "section_c":
        principles = _principle_queryset()
        section_c = BRSRSection.objects.filter(code="section_c", is_active=True).first()
        if principle_slug:
            principle = get_object_or_404(BRSRPrinciple, slug=principle_slug, is_active=True)
        else:
            principle = principles.first()
    return section, principle


def _question_queryset(section, principle=None):
    qs = (
        _pdf_questions_queryset().filter(section=section)
        .select_related("section", "principle", "parent_question")
        .order_by("display_order", "question_number")
    )
    if section.code == "section_c":
        if principle:
            qs = qs.filter(principle=principle)
        else:
            qs = qs.filter(principle__isnull=False)
    else:
        qs = qs.filter(principle__isnull=True)
    return qs


def _question_status(question, assignment=None):
    response_qs = QuestionResponse.objects.filter(question=question)
    if assignment is not None:
        response_qs = response_qs.filter(assignment=assignment)
    response = response_qs.select_related("assignment").order_by("-updated_at", "-created_at").first()
    if response:
        return response.status
    return "draft"


def _question_metadata(question):
    rules = question.validation_rules or {}
    return {
        "parent_question_id": question.parent_question.question_id if question.parent_question else "",
        "table_schema": rules.get("table_schema", {}) or {},
        "conditional_logic": rules.get("conditional_logic", {}) or {},
        "allowed_values": rules.get("allowed_values", []) or [],
        "units": rules.get("units", "") or "",
        "default_value": rules.get("default_value"),
        "component_type": rules.get("component_type", question.question_type),
        "source_excerpt": rules.get("source_excerpt", "") or "",
    }


def _workflow_counts(questions, assignment=None):
    question_ids = [q.id for q in questions]
    responses = QuestionResponse.objects.filter(question_id__in=question_ids)
    if assignment is not None:
        responses = responses.filter(assignment=assignment)
    total = len(question_ids)
    completed = responses.filter(status="approved").values("question_id").distinct().count()
    submitted = responses.filter(status__in=["submitted", "resubmitted"]).values("question_id").distinct().count()
    rejected = responses.filter(status="rejected").values("question_id").distinct().count()
    return {
        "total": total,
        "completed": completed,
        "submitted": submitted,
        "rejected": rejected,
        "progress": round((completed / total * 100), 1) if total else 0,
    }


def _assignment_missing_responses(assignment):
    if not assignment:
        return []

    questions = list(
        assignment.questions.select_related("section", "principle").order_by("display_order", "question_number")
    )
    responses = {response.question_id: response for response in assignment.responses.all()}
    missing = []
    for question in questions:
        response = responses.get(question.id)
        response_value = (response.response_value or "").strip() if response else ""
        response_json = response.response_json if response else {}
        if response and (response_value or response_json):
            continue
        missing.append(
            {
                "question_id": question.question_id,
                "question_number": question.question_number,
                "title": question.question_text,
                "section": question.section.name if question.section_id else "",
                "sub_section": question.sub_section or "",
            }
        )
    return missing


def _actor_content_type_map():
    return {
        "user": ContentType.objects.get_for_model(User),
        "department": ContentType.objects.get_for_model(Department),
        "plant": ContentType.objects.get_for_model(Plant),
    }


def _actor_label(actor):
    if not actor:
        return ""
    if hasattr(actor, "full_name") and actor.full_name:
        return actor.full_name
    if hasattr(actor, "name") and actor.name:
        return actor.name
    return str(actor)


def _get_assignment_scope(user):
    role_code = getattr(getattr(user, "role", None), "role_code", "") or ""
    if user.is_superuser or user.is_super_admin or role_code == "COMPANYADMIN":
        return "plant"
    if role_code in {"PLANT-COORD", "PLANT_COORD", "PLANTCOORD"}:
        return "department"
    if role_code in {"DEPT-APPR", "DEPT-USER", "DEPARTMENT-USER", "DEPARTMENT-APPR"}:
        return "user"
    if getattr(user, "department_id", None) and user.assigned_plants.exists():
        return "department"
    return "user"


def _assignment_scope_queryset(user, plant=None, department=None):
    role_code = getattr(getattr(user, "role", None), "role_code", "") or ""
    if user.is_superuser or user.is_super_admin or role_code == "COMPANYADMIN":
        return Assignment.objects.all()

    ct_map = _actor_content_type_map()
    filters = Q(assignee_content_type=ct_map["user"], assignee_object_id=user.id)
    reviewer_content_type = ContentType.objects.get_for_model(User)
    reviewer_assignments = Assignment.objects.filter(
        reviewer_links__reviewer_content_type=reviewer_content_type,
        reviewer_links__reviewer_object_id=user.id
    )
    filters |= Q(id__in=reviewer_assignments.values_list('id', flat=True))

    plant_ids = list(user.assigned_plants.filter(is_active=True).values_list("id", flat=True))
    if plant_ids:
        filters |= Q(assignee_content_type=ct_map["plant"], assignee_object_id__in=plant_ids)

    if getattr(user, "department_id", None):
        filters |= Q(
            assignee_content_type=ct_map["department"],
            assignee_object_id=user.department_id,
        )

    if plant:
        filters |= Q(plant=plant)
    if department:
        filters |= Q(assignee_content_type=ct_map["department"], assignee_object_id=department.id)
    return Assignment.objects.filter(filters).distinct()


def _plant_departments(plant):
    if not plant:
        return Department.objects.none()
    return (
        Department.objects.filter(users__assigned_plants=plant, is_active=True)
        .distinct()
        .order_by("name")
    )


def _assignment_target_role_codes(user):
    role_code = getattr(getattr(user, "role", None), "role_code", "") or ""
    if user.is_superuser or user.is_super_admin or role_code == "COMPANYADMIN":
        return ["PLANT-COORD", "PLANT_COORD", "PLANTCOORD"]
    if role_code in {"PLANT-COORD", "PLANT_COORD", "PLANTCOORD"}:
        return ["DEPT-APPR", "DEPT-USER", "DEPARTMENT-USER", "DEPARTMENT-APPR"]
    return ["DEPT-USER", "DEPT-APPR", "DEPARTMENT-USER", "DEPARTMENT-APPR"]


def _plant_assignees(plant, target_role_codes=None, current_user=None):
    if not plant:
        return User.objects.none()

    queryset = (
        User.objects.filter(is_active=True, assigned_plants=plant,)
        .exclude(Q(is_superuser=True) | Q(role__role_code__in=["SUPERADMIN", "COMPANYADMIN"]))
        .select_related("department", "role")
        .order_by("full_name", "username")
    )

    if target_role_codes:
        queryset = queryset.filter(role__role_code__in=target_role_codes)
    if current_user:
        queryset = queryset.exclude(pk=current_user.pk)

    return queryset.distinct()


def _default_assignee_for_context(user, plant):
    assignees = _plant_assignees(plant, target_role_codes=_assignment_target_role_codes(user), current_user=user)
    if not assignees.exists():
        return None

    role_rank = {
        "COMPANYADMIN": 0,
        "SUPERADMIN": 0,
        "PLANT-COORD": 1,
        "PLANT_COORD": 1,
        "DEPT-APPR": 2,
        "DEPT-USER": 3,
        "COMPANYUSER": 4,
    }

    def sort_key(item):
        role_code = getattr(getattr(item, "role", None), "role_code", "") or ""
        return (
            role_rank.get(role_code, 99),
            item.department_id or 999999,
            item.full_name or item.username,
        )

    return sorted(assignees, key=sort_key)[0]


def _serialize_assignment(assignment, user=None):
    questions = list(assignment.questions.select_related("section", "principle").order_by("display_order", "question_number"))
    first_question = questions[0] if questions else None
    workflow_task = assignment.workflow_task
    workflow_completed = bool(workflow_task and workflow_task.is_completed)
    assignment_status = getattr(assignment, "assignment_status", "") or ""
    assignment_status_label = {
        "pending": "Pending",
        "in_progress": "In Progress",
        "rejected": "Rejected",
        "reassigned": "Reassigned",
        "approved": "Approved",
    }.get(assignment_status, assignment_status.replace("_", " ").title() if assignment_status else "")
    response_map = {
        response.question_id: response.status
        for response in assignment.responses.all().only("question_id", "status")
    }
    if workflow_completed:
        workflow_status_label = "Final Approved & Locked"
    elif assignment.workflow_stage_type in {"pre_final_approval", "final_approval"}:
        workflow_status_label = "Completed"
    else:
        workflow_status_label = assignment_status_label or assignment.workflow_stage_label
    current_user_role = None

    if user and assignment.workflow_task and assignment.workflow_task.current_stage:
        stage_type = assignment.workflow_task.current_stage.stage_type

        if stage_type == "review" and _is_assigned_reviewer(user, assignment):
            current_user_role = "review"

        elif stage_type in ["approval", "pre_final_approval", "final_approval"]:
            task_info = _serialize_task_for_user(assignment.workflow_task, user)
            if task_info and task_info.get("can_act"):
                current_user_role = "approval"
    return {
        "id": assignment.id,
        "assignment_id": assignment.assignment_id,
        "plant": assignment.plant.name if assignment.plant_id else "",
        "plant_code": assignment.plant.code if assignment.plant_id else "",
        "assignee": "" if workflow_completed else _actor_label(assignment.assignee),
        "assignee_type": assignment.assignee_content_type.model if assignment.assignee_content_type_id else "",
        "assigner": _actor_label(assignment.assigner),
        "section": assignment.section.name if assignment.section_id else "",
        "section_code": assignment.section.code if assignment.section_id else "",
        "principle": assignment.principle.principle_name if assignment.principle_id else "",
        "financial_year": assignment.financial_year,
        "workflow_template": assignment.workflow_template_name,
        "workflow_stage": "" if workflow_completed else assignment.workflow_stage_label,
        "workflow_stage_type": "" if workflow_completed else assignment.workflow_stage_type,
        "workflow_status_label": workflow_status_label,
        "assignment_status": assignment_status,
        "assignment_status_label": assignment_status_label,
        "is_editable": assignment.is_editable,
        "is_assigned_reviewer": _is_assigned_reviewer(user, assignment) if user else False,
        "workflow_task": _serialize_workflow_task(workflow_task),
        "due_date": assignment.due_date.isoformat() if assignment.due_date else "",
        "priority": assignment.priority,
        "overall_status": assignment.overall_status,
        "is_overdue": assignment.is_overdue,
        "question_count": len(questions),
        "questions": [
            {
                "id": question.id,
                "question_id": question.question_id,
                "title": question.question_text,
                "number": question.question_number,
                "section_code": question.section.code,
                "principle_slug": question.principle.slug if question.principle else "",
                "status": response_map.get(question.id, "draft"),
            }
            for question in questions
        ],
        "workspace_url": (
            (
                reverse(
                    "brsr:question_workspace_principle",
                    kwargs={
                        "section_code": first_question.section.code,
                        "principle_slug": first_question.principle.slug,
                    },
                )
                if first_question and first_question.principle
                else reverse(
                    "brsr:question_workspace_section",
                    kwargs={"section_code": first_question.section.code},
                )
                if first_question
                else ""
            )
            + (f"?assignment_id={assignment.id}" if assignment.id else "")
        ),
        "current_user_role": current_user_role,
    }


def _serialize_assignment_with_reviewers(assignment, user=None):
    """Serialize assignment with reviewer information and comments."""
    base_data = _serialize_assignment(assignment, user)
    
    # Add reviewer information
    reviewer_links = assignment.reviewer_links.select_related('reviewer_content_type').all()
    reviewers = []
    for link in reviewer_links:
        reviewer = link.reviewer
        if reviewer:
            reviewers.append({
                "id": reviewer.id,
                "name": _actor_label(reviewer),
                "type": link.reviewer_content_type.model if link.reviewer_content_type_id else "user",
            })
    
    responses_with_comments = []
    for response in assignment.responses.select_related('question').all():
        if response.review_remark:  
            responses_with_comments.append({
                "question_id": response.question.question_id,
                "question_number": response.question.question_number,
                "question_text": response.question.question_text,
                "review_remark": response.review_remark,
                "reviewed_by": _actor_label(response.reviewed_by) if response.reviewed_by else "",
                "reviewed_at": response.reviewed_at.isoformat() if response.reviewed_at else "",
                "status": response.status,
            })
    
    base_data.update({
        "reviewers": reviewers,
        "review_comments": responses_with_comments,
        "has_review_comments": len(responses_with_comments) > 0,
        "is_assigned_reviewer": _is_assigned_reviewer(user, assignment) if user else False,
        "review_comments_count": len(responses_with_comments),
    })
    
    return base_data


def _assignment_context(section, principle, questions, assignment=None, user=None):
    latest_assignment = (
        Assignment.objects.filter(section=section, principle=principle)
        .select_related("plant")
        .order_by("-created_at")
        .first()
    )
    plant_qs = _company_scope_plants(user) if user else Plant.objects.filter(is_active=True).order_by("name")
    user_qs = User.objects.filter(is_active=True).select_related("role", "department").order_by(
        "full_name", "username"
    )
    fy_qs = FinancialYear.objects.all().order_by("-start_date")
    # Parent assignment / delegation removed from workflow
    return {
        "latest_assignment": latest_assignment,
        "current_assignment": assignment,
        "assignment_form": BRSRAssignmentForm(
            plant_queryset=plant_qs,
            user_queryset=user_qs,
            question_queryset=questions,
            financial_year_queryset=fy_qs,
        ),
        "plants": plant_qs,
        "users": user_qs,
        "financial_years": fy_qs,
        "assignment_schedule_form": AssignmentScheduleForm(
            plant_queryset=plant_qs,
            user_queryset=user_qs,
            question_queryset=questions,
            financial_year_queryset=fy_qs,
        ),
    }


def _is_section_locked_for_new_assignment(user, plant, section, principle, financial_year):
    """
    True if this plant/section/principle/financial_year combination has
    already been sent to (or past) Pre-Final Approval. Once locked, no new
    Assignment can be created for it — the existing one must go through the
    approval workflow instead of being duplicated.
    """
    if not plant or not section or not financial_year:
        return False

    assignments = list(
        _plant_scope_assignment_queryset(user, plant)
        .filter(section_id=section.id, financial_year=financial_year)
        .select_related("plant", "section", "principle", "workflow_template")
    )
    if principle:
        assignments = [a for a in assignments if a.principle_id == principle.id]
    else:
        assignments = [a for a in assignments if a.principle_id is None]

    locked_stages = {"pre_final_approval", "final_approval"}
    for assignment in assignments:
        _ensure_assignment_workflow_task(assignment, current_user=user)
        task = assignment.workflow_task
        if not task:
            continue
        if task.is_completed:
            return True
        if task.current_stage and task.current_stage.stage_type in locked_stages:
            return True
    return False


def _create_brsr_assignment(*, user, section, principle, cleaned_data, question_queryset, workflow_template_override=None):
    plant = cleaned_data["plant"]
    financial_year = cleaned_data["financial_year"]
    period_code = cleaned_data.get("period_code")
    if _is_section_locked_for_new_assignment(user, plant, section, principle, financial_year):
        raise ValueError(
            "This section has already been sent for Pre-Final Approval for this "
            "plant and financial year. No new assignment can be created until "
            "the current one is approved or rejected."
        )
    force_create = cleaned_data.get("force_create", False)
    workflow_template = workflow_template_override or _resolve_brsr_workflow_template(user=user, plant=plant)
    if not workflow_template:
        raise ValueError("No active BRSR workflow template is configured for this company.")
    if not workflow_template.first_stage:
        raise ValueError("The configured BRSR workflow template has no stages.")

    assignee = _resolve_brsr_assignee(
        plant,
        workflow_template,
        selected_assignee=cleaned_data.get("assignee"),
        current_user=user,
    )
    if assignee is None:
        raise ValueError(
            "No eligible assignee matches the first stage of the configured BRSR workflow."
        )

    reviewer = _resolve_brsr_reviewer(
        plant,
        workflow_template,
        selected_reviewer=cleaned_data.get("reviewer"),
        current_user=user,
    )

    if cleaned_data.get("reviewer") is not None and reviewer is None:
        raise ValueError(
            "The selected reviewer is not eligible for the review stage of this "
            "workflow (role/plant mismatch). Choose a different reviewer or "
            "update the workflow template's review-stage role."
        )

    user_ct = ContentType.objects.get_for_model(User)
    assigner = cleaned_data.get("assigner") or user
    existing = Assignment.objects.filter(
        plant=plant,
        section=section,
        principle=principle,
        financial_year=financial_year,
        period_code=period_code,
    ).order_by("-created_at").first()
    if existing:
        if existing.overall_status != 'completed':
            raise ValueError(
                "An active assignment already exists for this period. Please complete or close the existing assignment first."
            )
        if not force_create:
            raise ValueError(
                "This assignment has already been submitted for this period. "
                "Please confirm if you want to create another assignment."
            )
    assignment = Assignment.objects.create(
        plant=plant,
        principle=principle,
        section=section,
        financial_year=cleaned_data["financial_year"],
        workflow_template=workflow_template,
        data_collection_frequency=cleaned_data.get("data_collection_frequency") or "",
        assigner_content_type=user_ct,
        assigner_object_id=assigner.pk,
        assignee_content_type=user_ct,
        assignee_object_id=assignee.pk,
        due_date=cleaned_data.get("due_date"),
        priority=cleaned_data["priority"],
        notes=cleaned_data.get("notes"),
        period_code=period_code,
        period_label=cleaned_data.get("period_label"),
    )
    assignment.questions.set(question_queryset)
    if reviewer is not None:
        AssignmentReviewer.objects.create(
            assignment=assignment,
            reviewer_content_type=user_ct,
            reviewer_object_id=reviewer.pk,
        )
    for question in question_queryset:
        QuestionResponse.objects.get_or_create(
            assignment=assignment,
            question=question,
        )
    _ensure_assignment_workflow_task(assignment, current_user=user)
    _advance_assignment_to_entry_stage(assignment, actor=user)
    from .notifications import notify_assignment_created
    notify_assignment_created(assignment)
    
    return assignment


def _serialize_task_for_user(task, user):
    """Serialize workflow task with user permissions."""
    if not task:
        return None
    is_completed = bool(task.is_completed)
    stage_label = "Final Approved & Locked" if is_completed else (task.current_stage.label if task.current_stage_id else "")
    stage_type = "" if is_completed else (task.current_stage.stage_type if task.current_stage_id else "")

    assignee_id = task.current_assignee_object_id if (
        task.current_assignee_content_type_id and
        task.current_assignee_content_type.model == "user"  # Fixed typo here
    ) else None
    if is_completed:
        assignee_id = None

    is_admin = user.is_superuser or getattr(user, "is_super_admin", False)
    current_user_role_id = getattr(user, "role_id", None)
    current_stage_role_id = task.current_stage.role_id if task.current_stage_id else None

    if is_admin:
        can_act = user.is_authenticated
    elif task.current_stage_id and task.current_stage.stage_type in {"approval", "pre_final_approval", "final_approval"}:
        can_act = bool(
            user.is_authenticated
            and current_stage_role_id
            and current_user_role_id == current_stage_role_id
        )
    else:
        can_act = bool(user.is_authenticated and assignee_id == user.id)

    if task.is_returned and assignee_id == getattr(user, "id", None) and not is_admin:
        stage_ok = (
            not current_stage_role_id
            or current_user_role_id == current_stage_role_id
        )
        can_act = can_act or stage_ok
    if task.current_stage_id and task.current_stage.stage_type == "review":
        assignment = getattr(task.target, "assignment", None) or (task.target if isinstance(task.target, Assignment) else None)
        can_act = _is_assigned_reviewer(user, assignment)
    if is_completed:
        can_act = False

    return {
        "id": task.id,
        "stage": stage_label,
        "stage_type": stage_type,
        "stage_role_code": task.current_stage.role.role_code if (
            task.current_stage_id and task.current_stage.role_id
        ) else "",
        "current_assignee_id": assignee_id,
        "current_assignee": "" if is_completed else (str(task.current_assignee) if task.current_assignee else ""),
        "can_act": can_act,
        "is_completed": is_completed,
        "status_label": "Final Approved & Locked" if is_completed else stage_label,
    }

def _format_response_data(response_json):
    """Format response JSON as HTML for display."""
    if not response_json:
        return ""
    
    html_parts = []
    
    # Check if it's the trainingAwareness structure
    if isinstance(response_json, dict) and 'trainingAwareness' in response_json:
        data = response_json['trainingAwareness']
        if isinstance(data, list) and data and isinstance(data[0], dict):
            headers = list(data[0].keys())
            html_parts.append('<div class="data-table-container">')
            html_parts.append('<table class="data-table">')
            html_parts.append('<thead><tr><th>#</th>')
            for header in headers:
                html_parts.append(f'<th>{header}</th>')
            html_parts.append('</tr></thead>')
            html_parts.append('<tbody>')
            for idx, row in enumerate(data, 1):
                html_parts.append('<tr>')
                html_parts.append(f'<td>{idx}</td>')
                for header in headers:
                    value = row.get(header, "—")
                    html_parts.append(f'<td>{value}</td>')
                html_parts.append('</tr>')
            html_parts.append('</tbody>')
            html_parts.append('</table>')
            html_parts.append('</div>')
            return "".join(html_parts)
    
    # Handle other JSON structures as key-value pairs
    if isinstance(response_json, dict):
        html_parts.append('<div class="kv-container">')
        for key, value in response_json.items():
            if isinstance(value, list):
                html_parts.append(f'<div class="sub-section-title">{key}</div>')
                for idx, item in enumerate(value, 1):
                    if isinstance(item, dict):
                        html_parts.append(f'<div class="kv-row"><span class="kv-key">Entry {idx}</span>')
                        html_parts.append('<span class="kv-value">')
                        for sub_key, sub_value in item.items():
                            html_parts.append(f'{sub_key}: {sub_value}<br>')
                        html_parts.append('</span></div>')
                    else:
                        html_parts.append(f'<div class="kv-row"><span class="kv-key">{idx}</span><span class="kv-value">{item}</span></div>')
            else:
                html_parts.append(f'<div class="kv-row"><span class="kv-key">{key}</span><span class="kv-value">{value}</span></div>')
        html_parts.append('</div>')
        return "".join(html_parts)
    
    # Fallback: return as string
    return f'<div class="response-body response-value">{json.dumps(response_json, indent=2)}</div>'

def _fy_placeholders():
    today = date.today()
    start_year = today.year if today.month >= 4 else today.year - 1
    return {
        "{FY0}": f"{start_year}-{str(start_year + 1)[-2:]}",
        "{FY1}": f"{start_year - 1}-{str(start_year)[-2:]}",
        "{FY2}": f"{start_year - 2}-{str(start_year - 1)[-2:]}",
    }


def _replace_fy(text):
    if not isinstance(text, str) or not text:
        return text
    for token, value in _fy_placeholders().items():
        text = text.replace(token, value)
    return text


def _cell_text(value):
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return str(value)


def _readonly_table_html(field, response_json):
    columns = [_replace_fy(c) for c in (field.get("columns") or [])]
    rows = field.get("rows") or []
    has_groups = any((row.get("group") or "").strip() for row in rows)

    header_html = "<tr>" + "".join(f"<th>{escape(col)}</th>" for col in columns) + "</tr>"

    grouped = []
    sentinel = object()
    current_group = sentinel
    current_rows = []
    for row in rows:
        group_value = row.get("group")
        if group_value != current_group:
            if current_rows:
                grouped.append((current_group, current_rows))
            current_group = group_value
            current_rows = [row]
        else:
            current_rows.append(row)
    if current_rows:
        grouped.append((current_group, current_rows))

    body_html = ""
    for group_value, group_rows in grouped:
        row_count = len(group_rows)
        for idx, row in enumerate(group_rows):
            is_first = idx == 0
            row_label = _replace_fy(row.get("label") or "")
            row_html = "<tr>"
            for col_idx, col in enumerate(columns):
                if col_idx == 0:
                    if has_groups:
                        if is_first:
                            row_html += f'<td class="group-cell" rowspan="{row_count}">{escape(_replace_fy(group_value or ""))}</td>'
                    else:
                        row_html += f"<td>{escape(row_label)}</td>"
                elif col_idx == 1 and has_groups:
                    row_html += f'<td class="metrics-cell">{escape(row_label)}</td>'
                else:
                    field_data = next(
                        (f for f in (row.get("fields") or []) if _replace_fy(f.get("column")) == col),
                        None,
                    )
                    if field_data:
                        if field_data.get("type") == "static":
                            cell_value = field_data.get("value", "")
                        else:
                            raw_value = response_json.get(field_data.get("name"), "") if isinstance(response_json, dict) else ""
                            if field_data.get("type") == "select" and field_data.get("options"):
                                match = next(
                                    (opt for opt in field_data["options"] if str(opt.get("value", opt)) == str(raw_value)),
                                    None,
                                )
                                cell_value = match.get("label", raw_value) if match else raw_value
                            else:
                                cell_value = raw_value
                        cell_value = _cell_text(cell_value)
                        row_html += f"<td>{escape(cell_value) or '&mdash;'}</td>"
                    else:
                        row_html += "<td></td>"
            row_html += "</tr>"
            body_html += row_html

    return f'''<div class="form-group" data-field-type="table">
      <label class="form-label">{escape(_replace_fy(field.get("label") or ""))}</label>
      <div class="table-container">
        <table class="data-table">
          <thead>{header_html}</thead>
          <tbody>{body_html}</tbody>
        </table>
      </div>
    </div>'''


def _readonly_field_html(field, response_json):
    field_name = field.get("name") or ""
    field_label = _replace_fy(field.get("label") or field.get("name") or "")
    field_type = field.get("field_type") or field.get("type") or "text"
    kind = field.get("kind")
    value = response_json.get(field_name, "") if isinstance(response_json, dict) else ""

    if kind == "select":
        options = field.get("options") or []
        opts_html = "".join(
            f'<option value="{escape(_cell_text(opt.get("value", opt)))}" {"selected" if str(opt.get("value", opt)) == str(value) else ""}>{escape(_cell_text(opt.get("label", opt.get("value", opt))))}</option>'
            for opt in options
        )
        return f'''<div class="form-group" data-field-type="{escape(field_type)}">
          <label class="form-label">{escape(field_label)}</label>
          <select class="workspace-select" disabled>{opts_html}</select>
        </div>'''

    if kind == "radio":
        options = field.get("options") or []
        items = "".join(
            f'''<label class="choice-item"><input type="radio" disabled {"checked" if str(opt.get("value", opt)) == str(value) else ""}><span>{escape(_cell_text(opt.get("label", opt.get("value", opt))))}</span></label>'''
            for opt in options
        )
        return f'''<div class="form-group" data-field-type="{escape(field_type)}">
          <label class="form-label">{escape(field_label)}</label>
          <div class="choice-stack">{items}</div>
        </div>'''

    if kind == "checkbox_group":
        selected = value if isinstance(value, list) else [v.strip() for v in str(value or "").split(",") if v.strip()]
        selected = [str(s) for s in selected]
        items_list = field.get("items") or []
        items = "".join(
            f'''<label class="choice-item"><input type="checkbox" disabled {"checked" if str(item.get("value", item)) in selected else ""}><span>{escape(_cell_text(item.get("label", item.get("value", item))))}</span></label>'''
            for item in items_list
        )
        return f'''<div class="form-group" data-field-type="{escape(field_type)}">
          <label class="form-label">{escape(field_label)}</label>
          <div class="choice-stack">{items}</div>
        </div>'''

    if kind == "textarea":
        return f'''<div class="form-group" data-field-type="{escape(field_type)}">
          <label class="form-label">{escape(field_label)}</label>
          <textarea class="workspace-textarea form-textarea" readonly>{escape(_cell_text(value))}</textarea>
        </div>'''

    if kind == "input":
        input_type = "text" if field.get("type") == "calculated" else (field.get("type") or "text")
        return f'''<div class="form-group" data-field-type="{escape(field_type)}">
          <label class="form-label">{escape(field_label)}</label>
          <input class="workspace-input" type="{escape(input_type)}" value="{escape(_cell_text(value))}" readonly>
        </div>'''

    if kind == "table":
        return _readonly_table_html(field, response_json)

    return f'''<div class="form-group" data-field-type="{escape(field_type)}">
      <label class="form-label">{escape(field_label)}</label>
      <textarea class="workspace-textarea form-textarea" readonly>{escape(_cell_text(value))}</textarea>
    </div>'''


def _render_question_readonly_html(question, response):
    """
    Render a QuestionResponse read-only, using the exact same field
    definitions (validation_rules['fields']) the workspace uses, so the
    entered-data view looks identical to the workspace inputs — just
    disabled/readonly instead of editable.
    """
    if not response:
        return ""

    response_value = response.response_value or ""
    response_json = response.response_json or {}
    rules = question.validation_rules or {}
    fields = rules.get("fields") or []

    if fields:
        return '<div class="choice-stack">' + "".join(
            _readonly_field_html(field, response_json) for field in fields
        ) + '</div>'

    qtype = question.question_type
    options = question.options or []

    if qtype in ("textarea", "text"):
        return f'<div class="form-group"><textarea class="workspace-textarea form-textarea" readonly>{escape(response_value)}</textarea></div>'

    if qtype in ("number", "decimal", "currency", "percentage", "year", "email", "url", "date", "phone"):
        return f'<div class="form-group"><input class="workspace-input" type="text" value="{escape(response_value)}" readonly></div>'

    if qtype in ("radio", "yes_no"):
        items = "".join(
            f'''<label class="choice-item"><input type="radio" disabled {"checked" if str(opt.get("value", opt)) == str(response_value) else ""}><span>{escape(_cell_text(opt.get("label", opt.get("value", opt))))}</span></label>'''
            for opt in options
        )
        return f'<div class="form-group"><div class="choice-stack">{items}</div></div>'

    if qtype in ("checkbox", "multi_select"):
        selected = [v.strip() for v in str(response_value or "").split(",") if v.strip()]
        items = "".join(
            f'''<label class="choice-item"><input type="checkbox" disabled {"checked" if str(opt.get("value", opt)) in selected else ""}><span>{escape(_cell_text(opt.get("label", opt.get("value", opt))))}</span></label>'''
            for opt in options
        )
        return f'<div class="form-group"><div class="choice-stack">{items}</div></div>'

    if response_json:
        return _format_response_data(response_json)

    return f'<div class="form-group"><textarea class="workspace-textarea form-textarea" readonly>{escape(response_value)}</textarea></div>'

def _user_has_permission(user, code):
    if not user or not getattr(user, "is_authenticated", False):
        return False
    if user.is_superuser or getattr(user, "is_super_admin", False):
        return True
    role = getattr(user, "role", None)
    if not role:
        return False
    return role.permissions.filter(code=code).exists()


def _dashboard_plant_queryset(user):
    """
    Plants shown on the BRSR data dashboard:
      - superuser/company-admin -> every active plant in scope
      - everyone else -> only plants assigned to them, regardless of
        VIEW_ALL_BRSR_DATA (that permission no longer expands scope
        beyond the user's own assigned plants for non-admins).
    """
    if _is_admin_scope(user):
        return Plant.objects.filter(is_active=True).order_by("name")

    return user.assigned_plants.filter(is_active=True).order_by("name")


def _can_view_plant_brsr_data(user, plant):
    if _is_admin_scope(user):
        return True

    return user.assigned_plants.filter(pk=plant.pk, is_active=True).exists()

_MONTH_ORDER = {
    "JAN": 1, "FEB": 2, "MAR": 3, "APR": 4, "MAY": 5, "JUN": 6,
    "JUL": 7, "AUG": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DEC": 12,
}
_QUARTER_ORDER = {"Q1": 1, "Q2": 2, "Q3": 3, "Q4": 4}


def _period_sort_key(period_code):
    code = (period_code or "").upper()
    if code in _MONTH_ORDER:
        return (0, _MONTH_ORDER[code])
    if code in _QUARTER_ORDER:
        return (0, _QUARTER_ORDER[code])
    if code.startswith("WEEK-"):
        try:
            return (0, int(code.split("-")[1]))
        except (IndexError, ValueError):
            return (1, code)
    return (1, code)


def _try_float(value):
    if value is None or value == "":
        return None
    try:
        return float(str(value).replace(",", "").strip())
    except (TypeError, ValueError):
        return None


def _aggregate_response_values(values):
    """Sum a list of response_value strings if every non-empty one is
    numeric; otherwise fall back to the last non-empty value."""
    non_empty = [v for v in values if v not in (None, "")]
    numeric = [_try_float(v) for v in non_empty]
    if non_empty and all(n is not None for n in numeric):
        total = sum(numeric)
        return str(int(total)) if total == int(total) else str(total)
    for v in reversed(values):
        if v not in (None, ""):
            return v
    return ""


def _aggregate_response_jsons(response_jsons):
    """Merge a list of response_json dicts field-by-field:
    - numeric leaves are summed
    - list-of-dict values (table rows) are summed cell-by-cell where numeric,
      matched by row index
    - everything else: last non-empty value wins
    Works uniformly regardless of field 'kind' (input/textarea/radio/
    checkbox_group/select/table) since it only looks at the flat stored shape.
    """
    aggregated = {}
    for rj in response_jsons:
        if not isinstance(rj, dict):
            continue
        for key, value in rj.items():
            if isinstance(value, list):
                existing = aggregated.get(key)
                if not isinstance(existing, list):
                    aggregated[key] = [dict(row) if isinstance(row, dict) else row for row in value]
                    continue
                merged_rows = []
                for idx, row in enumerate(value):
                    if idx < len(existing) and isinstance(existing[idx], dict) and isinstance(row, dict):
                        merged_row = dict(existing[idx])
                        for cell_key, cell_val in row.items():
                            n_existing = _try_float(merged_row.get(cell_key))
                            n_new = _try_float(cell_val)
                            if n_existing is not None and n_new is not None:
                                merged_row[cell_key] = n_existing + n_new
                            elif cell_val not in (None, ""):
                                merged_row[cell_key] = cell_val
                        merged_rows.append(merged_row)
                    else:
                        merged_rows.append(row)
                aggregated[key] = merged_rows
            else:
                n_existing = _try_float(aggregated.get(key))
                n_new = _try_float(value)
                if n_existing is not None and n_new is not None:
                    aggregated[key] = n_existing + n_new
                elif value not in (None, ""):
                    aggregated[key] = value
    return aggregated


class _AggregatedResponse:
    """Lightweight stand-in for a QuestionResponse so the existing
    _render_question_readonly_html(question, response) renderer can be
    reused unchanged for the synthetic 'All periods' aggregate."""
    def __init__(self, response_value, response_json):
        self.response_value = response_value
        self.response_json = response_json


def _aggregate_response_stats(responses_qs):
    """Reduce a QuestionResponse queryset down to dashboard-friendly counts."""
    responses = list(
        responses_qs.only("question_id", "status", "response_value", "response_json", "updated_at")
    )
    entered_qids, approved_qids, pending_qids, rejected_qids = set(), set(), set(), set()
    last_updated = None

    for r in responses:
        has_data = bool((r.response_value or "").strip()) or bool(r.response_json)
        if not has_data:
            continue
        entered_qids.add(r.question_id)
        if r.status == "approved":
            approved_qids.add(r.question_id)
        elif r.status in ("submitted", "resubmitted"):
            pending_qids.add(r.question_id)
        elif r.status == "rejected":
            rejected_qids.add(r.question_id)
        if last_updated is None or (r.updated_at and r.updated_at > last_updated):
            last_updated = r.updated_at

    total = len(entered_qids)
    approved = len(approved_qids)
    return {
        "entered": total,
        "approved": approved,
        "pending_review": len(pending_qids),
        "rejected": len(rejected_qids),
        "progress": round((approved / total * 100), 1) if total else 0,
        "last_updated": last_updated,
    }


def _plant_brsr_stats(plant, financial_year=None):
    responses = QuestionResponse.objects.filter(assignment__plant=plant)
    if financial_year:
        responses = responses.filter(assignment__financial_year=financial_year)
    return _aggregate_response_stats(responses)


def _company_brsr_stats(plants, financial_year=None):
    responses = QuestionResponse.objects.filter(assignment__plant__in=plants)
    if financial_year:
        responses = responses.filter(assignment__financial_year=financial_year)
    return _aggregate_response_stats(responses)


def _build_brsr_data_groups(plants, financial_year=None):
    """
    Builds Section -> (Principle) -> Question rows of *already entered* data
    for the given plants. Each question row carries, per plant, every
    frequency period that has data (e.g. each month for a monthly-frequency
    assignment) plus an aggregated 'All periods' view — the template turns
    this into a period-selector dropdown per plant block.
    """
    assignments = Assignment.objects.filter(plant__in=plants)
    if financial_year:
        assignments = assignments.filter(financial_year=financial_year)
    assignments = assignments.select_related("plant").prefetch_related(
        "questions",
        "questions__section",
        "questions__principle",
        "responses",
        "responses__question",
    )

    question_meta = {}
    # question_id -> plant_id -> period_key -> entry
    question_plant_period_data = {}

    for assignment in assignments:
        responses_by_qid = {r.question_id: r for r in assignment.responses.all()}
        frequency = assignment.data_collection_frequency or ""
        period_code = assignment.period_code or ""
        period_label = assignment.period_label or period_code or assignment.financial_year

        for question in assignment.questions.all():
            response = responses_by_qid.get(question.id)
            if not response:
                continue
            has_data = bool((response.response_value or "").strip()) or bool(response.response_json)
            if not has_data:
                continue

            question_meta[question.id] = question
            plant_bucket = question_plant_period_data.setdefault(question.id, {})
            period_bucket = plant_bucket.setdefault(assignment.plant_id, {})
            key = period_code or f"__single__{assignment.id}"
            existing = period_bucket.get(key)
            if not existing or (response.updated_at and response.updated_at > existing["updated_at"]):
                period_bucket[key] = {
                    "plant": assignment.plant,
                    "response": response,
                    "financial_year": assignment.financial_year,
                    "updated_at": response.updated_at,
                    "frequency": frequency,
                    "period_code": period_code,
                    "period_label": period_label,
                }

    sections = {}
    for qid, question in question_meta.items():
        section = question.section
        principle = question.principle
        bucket = sections.setdefault(
            section.id, {"section": section, "principle_map": {}, "questions": []}
        )

        plant_period_map = question_plant_period_data[qid]

        all_frequencies = {
            entry["frequency"]
            for periods in plant_period_map.values()
            for entry in periods.values()
            if entry["frequency"]
        }
        has_frequency = bool(all_frequencies)

        plant_entries_payload = []
        for plant_id, periods in plant_period_map.items():
            period_entries = sorted(periods.values(), key=lambda e: _period_sort_key(e["period_code"]))
            plant = period_entries[0]["plant"]
            has_multiple_periods = len(period_entries) > 1

            period_payload = [
                {
                    "code": entry["period_code"] or "default",
                    "label": entry["period_label"],
                    "status": entry["response"].status,
                    "status_display": entry["response"].get_status_display(),
                    "response_html": _render_question_readonly_html(question, entry["response"]),
                    "reviewed_by": str(entry["response"].reviewed_by) if entry["response"].reviewed_by else "",
                    "financial_year": entry["financial_year"],
                }
                for entry in period_entries
            ]

            if has_multiple_periods:
                aggregated_response = _AggregatedResponse(
                    _aggregate_response_values([e["response"].response_value or "" for e in period_entries]),
                    _aggregate_response_jsons([e["response"].response_json or {} for e in period_entries]),
                )
                aggregated_html = _render_question_readonly_html(question, aggregated_response)
            else:
                aggregated_html = period_payload[0]["response_html"]

            latest_entry = max(period_entries, key=lambda e: e["updated_at"] or timezone.now())

            plant_entries_payload.append(
                {
                    "plant_name": plant.name,
                    "plant_code": plant.code,
                    "financial_year": latest_entry["financial_year"],
                    "frequency": latest_entry["frequency"],
                    "status": latest_entry["response"].status,
                    "status_display": latest_entry["response"].get_status_display(),
                    "response_value": latest_entry["response"].response_value or "",
                    "response_html": aggregated_html,
                    "reviewed_by": str(latest_entry["response"].reviewed_by) if latest_entry["response"].reviewed_by else "",
                    "has_multiple_periods": has_multiple_periods,
                    "periods": period_payload,
                }
            )

        plant_entries_payload.sort(key=lambda e: e["plant_name"])

        row = {
            "question_id": question.question_id,
            "number": question.question_number,
            "display_order": question.display_order,
            "title": question.question_text,
            "sub_section": question.sub_section or "",
            "dot_status": _aggregate_question_dot_status(plant_entries_payload),
            "has_frequency": has_frequency,
            "plant_entries": plant_entries_payload,
        }

        if principle:
            p_bucket = bucket["principle_map"].setdefault(
                principle.id, {"principle": principle, "questions": []}
            )
            p_bucket["questions"].append(row)
        else:
            bucket["questions"].append(row)

    ordered_sections = []
    for bucket in sections.values():
        bucket["questions"].sort(key=lambda r: (r["display_order"], r["number"]))
        principles = list(bucket["principle_map"].values())
        for p in principles:
            p["questions"].sort(key=lambda r: (r["display_order"], r["number"]))
        principles.sort(key=lambda p: p["principle"].principle_number)
        ordered_sections.append(
            {"section": bucket["section"], "principles": principles, "questions": bucket["questions"]}
        )
    ordered_sections.sort(key=lambda s: (s["section"].display_order, s["section"].code))
    return ordered_sections


_STATUS_DOT_PRIORITY = {"rejected": 3, "submitted": 2, "resubmitted": 2, "draft": 1, "approved": 0}


def _aggregate_question_dot_status(plant_entries):
    """Pick one representative status across all plant entries for a question,
    so the sidebar dot shows the most attention-worthy state."""
    if not plant_entries:
        return "draft"
    worst = plant_entries[0]["status"]
    worst_rank = _STATUS_DOT_PRIORITY.get(worst, 1)
    for entry in plant_entries[1:]:
        rank = _STATUS_DOT_PRIORITY.get(entry["status"], 1)
        if rank > worst_rank:
            worst = entry["status"]
            worst_rank = rank
    return worst

class BRSRDashboardView(LoginRequiredMixin, TemplateView):
    login_url = "accounts:login"
    template_name = "brsr/brsr_list.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        filters = _build_brsr_selection_filters(user, self.request)
        selected_plant = filters["selected_plant"]
        selected_financial_year = filters["selected_financial_year"]
        sections = _section_scope_queryset()
        principles = _principle_queryset()
        section_c = BRSRSection.objects.filter(code="section_c", is_active=True).first()

        section_cards = []
        for section in sections:
            question_count = _question_queryset(section).count()
            send_enabled, assignment_count = _section_principle_ready_for_pre_final(
                user,
                selected_plant,
                section,
                None,
                selected_financial_year,
            )
            section_cards.append(
                {
                    "section": section,
                    "question_count": question_count,
                    "url": reverse("brsr:question_workspace_section", kwargs={"section_code": section.code}),
                    "send_enabled": send_enabled,
                    "assignment_count": assignment_count,
                    "ready_for_pre_final": send_enabled,
                    "selected_plant_id": filters["selected_plant_id"],
                    "selected_financial_year": selected_financial_year,
                    "send_url": reverse("brsr:send_pre_final_approval"),
                }
            )

        principle_cards = []
        for principle in principles:
            send_enabled, assignment_count = _section_principle_ready_for_pre_final(
                user,
                selected_plant,
                section_c or _get_default_section(),
                principle,
                selected_financial_year,
            )
            principle_cards.append(
                {
                    "principle": principle,
                    "question_count": principle.questions.filter(is_active=True).count(),
                    "url": reverse(
                        "brsr:question_workspace_principle",
                        kwargs={"section_code": "section_c", "principle_slug": principle.slug},
                    ),
                    "send_enabled": send_enabled,
                    "assignment_count": assignment_count,
                    "ready_for_pre_final": send_enabled,
                    "selected_plant_id": filters["selected_plant_id"],
                    "selected_financial_year": selected_financial_year,
                    "send_url": reverse("brsr:send_pre_final_approval"),
                }
            )

        context["section_cards"] = section_cards
        context["principle_cards"] = principle_cards
        context["workspace_url"] = reverse("brsr:question_workspace")
        context["total_questions"] = _pdf_questions_queryset().count()
        context["total_sections"] = sections.count()
        context["total_principles"] = principles.count()
        context["plants"] = filters["plants"]
        context["financial_years"] = filters["financial_years"]
        context["selected_plant"] = selected_plant
        context["selected_plant_id"] = filters["selected_plant_id"]
        context["selected_financial_year"] = selected_financial_year
        return context


class ApprovalBundleDetailView(LoginRequiredMixin, TemplateView):
    login_url = "accounts:login"
    template_name = "brsr/approval_bundle_detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        stage_type = kwargs.get("stage_type")
        company_id = kwargs.get("company_id")
        section_code = kwargs.get("section_code")
        financial_year = self.request.GET.get("financial_year", "")
        principle_slug = self.request.GET.get("principle", "")

        assignments = _approval_bundle_assignments(
            user,
            str(company_id),
            section_code,
            financial_year,
            principle_slug=principle_slug,
            stage_type=stage_type,
        )
        if not assignments:
            raise PermissionDenied("No approval bundle found for this page.")

        company = get_object_or_404(Company, pk=company_id)
        section = assignments[0].section
        principle = assignments[0].principle if principle_slug else None

        bundle_assignments = []
        question_total = 0
        for assignment in assignments:
            responses = {
                response.question_id: response
                for response in assignment.responses.select_related("question").prefetch_related("documents")
            }
            questions = []
            for question in assignment.questions.select_related("section", "principle").order_by("display_order", "question_number"):
                response = responses.get(question.id)
                questions.append(
                    _serialize_consolidated_bundle_question(
                        question,
                        response=response,
                        assignment=assignment,
                        user=user,
                    )
                )
            question_total += len(questions)
            bundle_assignments.append(
                {
                    "assignment": _serialize_assignment(assignment, user),
                    "questions": questions,
                }
            )

        context.update(
            {
                "stage_type": stage_type,
                "company": company,
                "section": section,
                "principle": principle,
                "financial_year": financial_year,
                "bundle_assignments": bundle_assignments,
                "question_total": question_total,
                "assignment_total": len(bundle_assignments),
                "stage_label": "Pre-Final Approval" if stage_type == "pre_final_approval" else "Final Approval",
                "approve_url": reverse("brsr:approve_consolidated_bundle"),
                "reject_url": reverse("brsr:reject_consolidated_bundle"),
                "approval_dashboard_url": reverse("brsr:approval_dashboard"),
            }
        )
        return context


class AssignmentDashboardView(LoginRequiredMixin, TemplateView):
    login_url = "accounts:login"
    template_name = "brsr/assignment_dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        plant_filter = self.request.GET.get('plant', '')
        status_filter = self.request.GET.get('status', '')
        stage_filter = self.request.GET.get('stage', '')
        search_query = self.request.GET.get('search', '').strip()
        
        assignments = list(
            _my_dashboard_assignment_queryset(user)
            .select_related(
                "plant",
                "section",
                "principle",
                "workflow_template",
                "assignee_content_type",
                "assigner_content_type",
            )
            .prefetch_related(
                "questions",
                "responses",
                "questions__section",
                "questions__principle",
                "responses__question",
                "reviewer_links",
                "reviewer_links__reviewer_content_type",
            )
        )
        
        if plant_filter:
            assignments = [a for a in assignments if a.plant_id and str(a.plant_id) == plant_filter]
        
        if status_filter:
            assignments = [a for a in assignments if a.overall_status == status_filter]
        
        if stage_filter:
            assignments = [a for a in assignments if a.workflow_stage_type == stage_filter]
        
        if search_query:
            search_lower = search_query.lower()
            assignments = [
                a for a in assignments
                if search_lower in a.assignment_id.lower()
                or (a.assignee and search_lower in str(a.assignee).lower())
                or any(
                    search_lower in str(link.reviewer).lower()
                    for link in a.reviewer_links.all()
                    if link.reviewer
                )
            ]
        
        assignments.sort(key=lambda x: (x.overall_status == "completed", -x.created_at.timestamp()))
        plants = _company_scope_plants(user) if _is_admin_scope(user) else user.assigned_plants.filter(is_active=True).order_by("name")
        statuses = sorted(set(a.overall_status for a in assignments if a.overall_status))
        stages = sorted(set(a.workflow_stage_type for a in assignments if a.workflow_stage_type))    
        serialized_assignments = [
            _serialize_assignment_with_reviewers(assignment, user)
            for assignment in assignments
        ]
        
        context.update({
            "assignments": serialized_assignments,
            "assignment_count": len(serialized_assignments),
            "open_count": sum(1 for item in serialized_assignments if item["overall_status"] != "completed"),
            "completed_count": sum(1 for item in serialized_assignments if item["overall_status"] == "completed"),
            "overdue_count": sum(1 for item in serialized_assignments if item["is_overdue"]),
            "assignment_scope": _get_assignment_scope(user),
            "plants": plants,
            "statuses": statuses,
            "stages": stages,
            "selected_plant": plant_filter,
            "selected_status": status_filter,
            "selected_stage": stage_filter,
            "search_query": search_query,
        })
        return context


def send_pre_final_approval(request):
    if request.method != "POST":
        return redirect("brsr:brsr_list")

    user = request.user
    plant_id = request.POST.get("plant_id")
    section_code = request.POST.get("section_code")
    principle_slug = request.POST.get("principle_slug")
    financial_year = request.POST.get("financial_year")

    plant = get_object_or_404(_company_scope_plants(user), pk=plant_id) if plant_id else None
    section = get_object_or_404(BRSRSection, code=section_code, is_active=True) if section_code else None
    principle = get_object_or_404(BRSRPrinciple, slug=principle_slug, is_active=True) if principle_slug else None

    if not plant or not section or not financial_year:
        messages.error(request, "Incomplete pre-final approval bundle.")
        return redirect("brsr:brsr_list")

    assignments = _section_principle_assignments_for_pre_final(user, plant, section, principle, financial_year)
    ready, assignment_count = _section_principle_ready_for_pre_final(user, plant, section, principle, financial_year)
    if not ready:
        messages.error(request, "This section/principle is not ready to be sent for Pre-Final Approval yet.")
        return redirect("brsr:brsr_list")

    next_stage_type = "pre_final_approval"
    transitioned = 0
    recipients = {}
    for assignment in assignments:
        _ensure_assignment_workflow_task(assignment, current_user=user)
        task = assignment.workflow_task
        if not task or task.is_completed:
            continue
        if not task.current_stage or task.current_stage.stage_type != "approval":
            continue

        next_stage = task.current_stage.next_stage()
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
            remark=f"Section {section.name} sent for pre-final approval.",
            next_assignee=next_assignee,
        )
        transitioned += 1
        if next_assignee and getattr(next_assignee, "email", None):
            recipients.setdefault(next_assignee.id, next_assignee)
        elif next_stage:
            for eligible in _workflow_assignees_for_stage(assignment.plant, next_stage, current_user=user, assignment=assignment):
                if getattr(eligible, "email", None):
                    recipients.setdefault(eligible.id, eligible)

    from .notifications import notify_section_sent_for_pre_final
    notify_section_sent_for_pre_final(
        assignments=assignments,
        recipients=list(recipients.values()),
        plant=plant,
        section=section,
        principle=principle,
        financial_year=financial_year,
        sent_by=user,
    )

    messages.success(
        request,
        f"{transitioned} assignment{'' if transitioned == 1 else 's'} were sent for Pre-Final Approval."
    )

    query = {
        "stage": next_stage_type,
        "plant": str(plant.id),
        "section": section.code,
        "financial_year": financial_year,
    }
    if principle:
        query["principle"] = principle.slug
    return redirect(f"{reverse('brsr:approval_dashboard')}?{urlencode(query)}")


def approve_consolidated_bundle(request):
    if request.method != "POST":
        return redirect("brsr:approval_dashboard")

    user = request.user
    company_id = request.POST.get("company_id")
    section_code = request.POST.get("section_code")
    principle_slug = request.POST.get("principle_slug") or ""
    financial_year = request.POST.get("financial_year")
    stage_type = request.POST.get("stage_type")

    if stage_type not in {"pre_final_approval", "final_approval"}:
        messages.error(request, "Invalid approval stage.")
        return redirect("brsr:approval_dashboard")
    if not company_id or not section_code or not financial_year:
        messages.error(request, "Incomplete approval bundle.")
        return redirect("brsr:approval_dashboard")

    company = get_object_or_404(Company, pk=company_id)
    assignments = _approval_bundle_assignments(
        user,
        company_id,
        section_code,
        financial_year,
        principle_slug=principle_slug,
        stage_type=stage_type,
    )
    if not assignments:
        messages.error(request, "No assignments were found for this approval bundle.")
        return redirect("brsr:approval_dashboard")

    transitioned = 0
    submitted_notifications = []
    approved_notifications = []

    from .notifications import notify_assignment_approved, notify_assignment_submitted

    try:
        with transaction.atomic():
            for assignment in assignments:
                _ensure_assignment_workflow_task(assignment, current_user=user)
                task = assignment.workflow_task
                if not task or task.is_completed:
                    continue
                if not task.current_stage or task.current_stage.stage_type != stage_type:
                    continue

                next_stage = task.current_stage.next_stage() if task.current_stage_id else None
                while next_stage and next_stage.stage_type == "review":
                    next_stage = _next_non_review_stage(next_stage)

                next_assignee = None
                if next_stage:
                    next_assignee = _first_workflow_assignee_for_stage(
                        assignment.plant,
                        next_stage,
                        current_user=user,
                        assignment=assignment,
                    )

                WorkflowConfigurationEngine.approve(task, user, next_assignee=next_assignee)
                assignment.refresh_from_db()
                transitioned += 1

                if next_assignee and assignment.workflow_task and not assignment.workflow_task.is_completed:
                    submitted_notifications.append((assignment, next_assignee))
                if assignment.workflow_task and assignment.workflow_task.is_completed:
                    approved_notifications.append(assignment)
    except (PermissionDenied, ValueError) as exc:
        messages.error(request, str(exc))
        return redirect("brsr:approval_dashboard")

    if transitioned == 0:
        messages.error(request, "No assignments could be advanced for this bundle.")
        return redirect("brsr:approval_dashboard")

    for assignment, next_assignee in submitted_notifications:
        notify_assignment_submitted(assignment, next_assignee)
    for assignment in approved_notifications:
        notify_assignment_approved(assignment)

    messages.success(
        request,
        f"{transitioned} assignment{'' if transitioned == 1 else 's'} in {company.company_name} were approved."
    )

    query = {
        "stage": "final_approval" if stage_type == "pre_final_approval" else stage_type,
        "company": company_id,
        "section": section_code,
        "financial_year": financial_year,
    }
    if principle_slug:
        query["principle"] = principle_slug
    return redirect(f"{reverse('brsr:approval_dashboard')}?{urlencode(query)}")


def reject_consolidated_bundle(request):
    if request.method != "POST":
        return redirect("brsr:approval_dashboard")

    user = request.user
    company_id = request.POST.get("company_id")
    section_code = request.POST.get("section_code")
    principle_slug = request.POST.get("principle_slug") or ""
    financial_year = request.POST.get("financial_year")
    stage_type = request.POST.get("stage_type")
    remark = (request.POST.get("remark") or "").strip()

    if stage_type not in {"pre_final_approval", "final_approval"}:
        messages.error(request, "Invalid approval stage.")
        return redirect("brsr:approval_dashboard")
    if not company_id or not section_code or not financial_year:
        messages.error(request, "Incomplete approval bundle.")
        return redirect("brsr:approval_dashboard")
    if not remark:
        messages.error(request, "A rejection remark is required.")
        return redirect("brsr:approval_dashboard")

    company = get_object_or_404(Company, pk=company_id)
    assignments = _approval_bundle_assignments(
        user,
        company_id,
        section_code,
        financial_year,
        principle_slug=principle_slug,
        stage_type=stage_type,
    )
    if not assignments:
        messages.error(request, "No assignments were found for this approval bundle.")
        return redirect("brsr:approval_dashboard")

    transitioned = 0
    try:
        with transaction.atomic():
            for assignment in assignments:
                _ensure_assignment_workflow_task(assignment, current_user=user)
                task = assignment.workflow_task
                if not task or task.is_completed:
                    continue
                if not task.current_stage or task.current_stage.stage_type != stage_type:
                    continue

                return_to_stage = task.template.stages.filter(stage_type="data_entry").first() if task.template_id else None
                WorkflowConfigurationEngine.reject(
                    task,
                    user,
                    remark=remark,
                    return_to_stage=return_to_stage,
                    return_to_assignee=assignment.assignee,
                )
                assignment.refresh_from_db()
                transitioned += 1
    except (PermissionDenied, ValueError) as exc:
        messages.error(request, str(exc))
        return redirect("brsr:approval_dashboard")

    if transitioned == 0:
        messages.error(request, "No assignments could be rejected for this bundle.")
        return redirect("brsr:approval_dashboard")

    messages.success(
        request,
        f"{transitioned} assignment{'' if transitioned == 1 else 's'} in {company.company_name} were rejected."
    )
    query = {
        "stage": stage_type,
        "company": company_id,
        "section": section_code,
        "financial_year": financial_year,
    }
    if principle_slug:
        query["principle"] = principle_slug
    return redirect(f"{reverse('brsr:approval_dashboard')}?{urlencode(query)}")


class ApprovalDashboardView(LoginRequiredMixin, TemplateView):
    login_url = "accounts:login"
    template_name = "brsr/approval_dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        company_filter = self.request.GET.get('company', '')
        plant_filter = self.request.GET.get('plant', '')
        section_filter = self.request.GET.get('section', '')
        financial_year_filter = self.request.GET.get('financial_year', '')
        stage_filter = self.request.GET.get('stage', '')
        search_query = self.request.GET.get('search', '').strip()
        
        # Get all assignments in approval stages that the user can act on
        assignments = []
        for assignment in _my_dashboard_assignment_queryset(user).select_related(
            "plant",
            "section",
            "principle",
            "workflow_template",
            "assignee_content_type",
            "assigner_content_type",
        ).prefetch_related(
            "questions",
            "responses",
            "questions__section",
            "questions__principle",
        ):
            # Check if assignment is in an approval stage
            if not assignment.workflow_stage_type or not _is_approval_stage(assignment.workflow_stage_type):
                continue
            
            # Check if user can act on this assignment
            if not _can_user_act_on_assignment(user, assignment):
                continue
            
            # Skip completed assignments
            if assignment.workflow_task and assignment.workflow_task.is_completed:
                continue
                
            assignments.append(assignment)
        
        # Apply filters
        if company_filter:
            assignments = [
                a for a in assignments
                if getattr(getattr(a.plant, "created_by", None), "company", None) 
                and str(getattr(getattr(a.plant, "created_by", None), "company", None).id) == company_filter
            ]
        
        if plant_filter:
            assignments = [a for a in assignments if a.plant_id and str(a.plant_id) == plant_filter]

        if section_filter:
            assignments = [a for a in assignments if a.section_id and a.section.code == section_filter]

        if financial_year_filter:
            assignments = [a for a in assignments if a.financial_year == financial_year_filter]
        
        if stage_filter:
            assignments = [a for a in assignments if a.workflow_stage_type == stage_filter]
        
        if search_query:
            search_lower = search_query.lower()
            assignments = [
                a for a in assignments
                if search_lower in a.assignment_id.lower()
                or (a.assignee and search_lower in str(a.assignee).lower())
                or any(
                    search_lower in str(link.reviewer).lower()
                    for link in a.reviewer_links.all()
                    if link.reviewer
                )
            ]
        
        grouped = {}
        total_questions = 0
        stage_counts = {
            "review": 0,
            "approval": 0,
            "pre_final_approval": 0,
            "final_approval": 0,
        }
        consolidated_pre_final_groups = []
        consolidated_final_groups = []
        
        companies = set()
        plants = set()
        
        for assignment in assignments:
            stage_type = assignment.workflow_stage_type or ""
            if stage_type in stage_counts:
                stage_counts[stage_type] += 1
            
            company = getattr(getattr(assignment.plant, "created_by", None), "company", None)
            company_key = company.company_name if company else "Unknown Company"
            company_id = str(company.id) if company else ""
            
            companies.add((company_id, company_key))
            
            plant_key = assignment.plant.name if assignment.plant_id else "Unknown Plant"
            plant_id = str(assignment.plant.id) if assignment.plant_id else ""
            plants.add((plant_id, plant_key))

            questions_qs = assignment.questions.select_related("section", "principle").order_by("display_order", "question_number")
            assignment_data = _serialize_assignment(assignment, user)
            responses = {
                response.question_id: response
                for response in assignment.responses.select_related("question")
            }
            question_rows = []
            for question in questions_qs:
                response = responses.get(question.id)
                question_rows.append(
                    {
                        "question_id": question.question_id,
                        "title": question.question_text,
                        "number": question.question_number,
                        "status": response.status if response else "draft",
                        "status_display": "Final Approved & Locked" if (assignment.workflow_task and assignment.workflow_task.is_completed) else ((response.status if response else "draft").replace("_", " ").title()),
                        "workflow_stage": "Final Approved & Locked" if (assignment.workflow_task and assignment.workflow_task.is_completed) else assignment.workflow_stage_label,
                        "workflow_stage_type": "" if (assignment.workflow_task and assignment.workflow_task.is_completed) else assignment.workflow_stage_type,
                        "response_value": response.response_value if response else "",
                        "response_json": response.response_json if response else {},
                        "review_remark": response.review_remark if response else "",
                        "assignment_id": assignment.id,
                    }
                )

            if stage_type == "pre_final_approval":
                section_key = assignment.section.name if assignment.section else "Unknown Section"
                principle_key = assignment.principle.principle_name if assignment.principle else "Section-wide"
                entry = next(
                    (
                        item for item in consolidated_pre_final_groups
                        if item["company_name"] == company_key
                        and item["section_name"] == section_key
                        and item["principle_name"] == principle_key
                    ),
                    None,
                )
                if entry is None:
                    consolidated_pre_final_groups.append(
                        {
                            "company_name": company_key,
                            "company_id": company_id,
                            "section_name": section_key,
                            "section_code": assignment.section.code if assignment.section_id else "",
                            "principle_name": principle_key,
                            "principle_slug": assignment.principle.slug if assignment.principle_id else "",
                            "financial_year": assignment.financial_year,
                            "bundle_detail_url": "",
                            "plant_names": set([plant_key]),
                            "assignment_count": 1,
                            "assignment_id": assignment.id,
                            "assignments": [
                                {
                                    "assignment": assignment_data,
                                    "questions": question_rows,
                                }
                            ],
                        }
                    )
                else:
                    entry["plant_names"].add(plant_key)
                    entry["assignment_count"] += 1
                    entry.setdefault("assignments", []).append(
                        {
                            "assignment": assignment_data,
                            "questions": question_rows,
                        }
                    )
                total_questions += questions_qs.count()
                continue

            if stage_type == "final_approval":
                section_key = assignment.section.name if assignment.section else "Unknown Section"
                principle_key = assignment.principle.principle_name if assignment.principle else "Section-wide"
                entry = next(
                    (
                        item for item in consolidated_final_groups
                        if item["company_name"] == company_key
                        and item["section_name"] == section_key
                        and item["principle_name"] == principle_key
                    ),
                    None,
                )
                if entry is None:
                    consolidated_final_groups.append(
                        {
                            "company_name": company_key,
                            "company_id": company_id,
                            "section_name": section_key,
                            "section_code": assignment.section.code if assignment.section_id else "",
                            "principle_name": principle_key,
                            "principle_slug": assignment.principle.slug if assignment.principle_id else "",
                            "financial_year": assignment.financial_year,
                            "bundle_detail_url": "",
                            "plant_names": set([plant_key]),
                            "assignment_count": 1,
                            "assignment_id": assignment.id,
                            "assignments": [
                                {
                                    "assignment": assignment_data,
                                    "questions": question_rows,
                                }
                            ],
                        }
                    )
                else:
                    entry["plant_names"].add(plant_key)
                    entry["assignment_count"] += 1
                    entry.setdefault("assignments", []).append(
                        {
                            "assignment": assignment_data,
                            "questions": question_rows,
                        }
                    )
                total_questions += questions_qs.count()
                continue
            
            # Regular review/approval assignments
            company_bucket = grouped.setdefault(company_key, {})
            company_bucket["_company_id"] = company_id
            plant_bucket = company_bucket.setdefault(plant_key, {})
            plant_bucket["_plant_id"] = plant_id
            entries = plant_bucket.setdefault("entries", [])
            total_questions += len(question_rows)
            entries.append(
                {
                    "assignment": assignment_data,
                    "questions": question_rows,
                }
            )
        
        plants_list = sorted([{"id": p_id, "name": p_name} for p_id, p_name in plants if p_id], key=lambda x: x["name"])
        companies_list = sorted([{"id": c_id, "name": c_name} for c_id, c_name in companies if c_id], key=lambda x: x["name"])
        
        # Convert sets to sorted lists
        consolidated_pre_final_groups = [
            {
                **item,
                "plant_names": sorted(item["plant_names"]),
            }
            for item in consolidated_pre_final_groups
        ]
        consolidated_final_groups = [
            {
                **item,
                "plant_names": sorted(item["plant_names"]),
            }
            for item in consolidated_final_groups
        ]

        for item in consolidated_pre_final_groups:
            query = {"financial_year": item["financial_year"]}
            if item.get("principle_slug"):
                query["principle"] = item["principle_slug"]
            item["bundle_detail_url"] = (
                reverse(
                    "brsr:approval_bundle_detail",
                    kwargs={
                        "stage_type": "pre_final_approval",
                        "company_id": item["company_id"],
                        "section_code": item["section_code"],
                    },
                )
                + f"?{urlencode(query)}"
            )

        for item in consolidated_final_groups:
            query = {"financial_year": item["financial_year"]}
            if item.get("principle_slug"):
                query["principle"] = item["principle_slug"]
            item["bundle_detail_url"] = (
                reverse(
                    "brsr:approval_bundle_detail",
                    kwargs={
                        "stage_type": "final_approval",
                        "company_id": item["company_id"],
                        "section_code": item["section_code"],
                    },
                )
                + f"?{urlencode(query)}"
            )

        stages = sorted([s for s in stage_counts.keys() if stage_counts[s] > 0])
        
        context.update({
            "grouped_assignments": grouped,
            "consolidated_pre_final_groups": consolidated_pre_final_groups,
            "consolidated_final_groups": consolidated_final_groups,
            "can_view_pre_final_approvals": bool(
                user.is_superuser
                or getattr(user, "is_super_admin", False)
                or ApprovalConfigurationTask.objects.filter(
                    current_stage__stage_type="pre_final_approval",
                    current_stage__role_id=getattr(user, "role_id", None),
                ).exists()
            ),
            "can_view_final_approvals": bool(
                user.is_superuser
                or getattr(user, "is_super_admin", False)
                or ApprovalConfigurationTask.objects.filter(
                    current_stage__stage_type="final_approval",
                    current_stage__role_id=getattr(user, "role_id", None),
                ).exists()
            ),
            "assignment_count": len(assignments),
            "question_count": total_questions,
            "stage_counts": stage_counts,
            "approval_stage_count": (
                stage_counts["approval"]
                + stage_counts["pre_final_approval"]
                + stage_counts["final_approval"]
            ),
            "companies": companies_list,
            "plants": plants_list,
            "stages": stages,
            "selected_company": company_filter,
            "selected_plant": plant_filter,
            "selected_section": section_filter,
            "selected_financial_year": financial_year_filter,
            "selected_stage": stage_filter,
            "search_query": search_query,
        })
        return context

class AssignmentDetailView(LoginRequiredMixin, TemplateView):
    """
    View for showing all submitted questions for a specific assignment.
    """
    login_url = "accounts:login"
    template_name = "brsr/assignment_detail.html "
    success_url = "brsr:approval_dashboard"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        assignment_id = kwargs.get('assignment_id')
        user = self.request.user

        # Get the assignment with proper permissions
        assignment = get_object_or_404(
            _my_dashboard_assignment_queryset(user).select_related(
                "plant",
                "section",
                "principle",
                "workflow_template",
                "assignee_content_type",
                "assigner_content_type",
            ).prefetch_related(
                "questions",
                "questions__section",
                "questions__principle",
                "responses",
                "responses__question",
                "responses__documents",
            ),
            pk=assignment_id
        )

        # Ensure workflow task exists
        _ensure_assignment_workflow_task(assignment, current_user=user)

        # Get all questions and their responses
        questions = list(
            assignment.questions.select_related("section", "principle")
            .order_by("display_order", "question_number")
        )

        # Build a map of question_id to response
        responses = {
            response.question_id: response
            for response in assignment.responses.select_related("question")
        }

        question_rows = []
        for question in questions:
            response = responses.get(question.id)

            # Get the response data
            response_value = ""
            response_json = {}
            has_response = False
            answered_by = ""

            if response:
                if response.response_value:
                    response_value = response.response_value
                    has_response = True

                if response.response_json:
                    response_json = response.response_json
                    has_response = True

                if response.answered_by:
                    answered_by = str(response.answered_by)
 
            documents = []
            if response:
                documents = [
                    {
                        "id": doc.id,
                        "name": doc.original_name,
                        "url": doc.document.url,
                    }
                    for doc in response.documents.all()
                ]
 
            question_rows.append({
                "question_id": question.question_id,
                "title": question.question_text,
                "number": question.question_number,
                "question_type": question.question_type,
                "sub_section": question.sub_section or "",
                "options": question.options or [],
                "validation_rules": question.validation_rules or {},
                "status": response.status if response else "draft",
                "status_display": "Final Approved & Locked" if (assignment.workflow_task and assignment.workflow_task.is_completed) else ((response.status if response else "draft").replace("_", " ").title()),
                "workflow_stage": "Final Approved & Locked" if (assignment.workflow_task and assignment.workflow_task.is_completed) else assignment.workflow_stage_label,
                "workflow_stage_type": "" if (assignment.workflow_task and assignment.workflow_task.is_completed) else assignment.workflow_stage_type,
                "response_value": response_value,
                "response_json": response_json,
                "has_response": has_response,
                "answered_by": answered_by,
                "documents": documents,
                "review_remark": response.review_remark if response else "",
                "submitted_by": str(response.submitted_by) if response and response.submitted_by else "",
                "submitted_at": response.submitted_at if response else None,
                "reviewed_by": str(response.reviewed_by) if response and response.reviewed_by else "",
                "reviewed_at": response.reviewed_at if response else None,
                "can_act": self._can_act_on_question(assignment, response, user),
            })

        context["assignment"] = _serialize_assignment(assignment, user)
        context["questions"] = question_rows

        context["question_groups"] = self._group_questions(question_rows)
 
        context["questions_json"] = [
            {
                "question_id": q["question_id"],
                "question_number": q["number"],
                "title": q["title"],
                "question_type": q["question_type"],
                "sub_section": q["sub_section"],
                "options": q["options"],
                "validation_rules": q["validation_rules"],
                "response_value": q["response_value"],
                "response_json": q["response_json"],
            }
            for q in question_rows
        ]

        context["question_count"] = len(question_rows)
        context["plant_name"] = assignment.plant.name if assignment.plant_id else ""
        context["company_name"] = getattr(
            getattr(assignment.plant, "created_by", None),
            "company_name",
            ""
        )
        
        # Counts for summary
        status_counts = {
            "draft": 0,
            "submitted": 0,
            "approved": 0,
            "rejected": 0,
            "resubmitted": 0,
        }
        for q in question_rows:
            status = q.get("status", "draft")
            if status in status_counts:
                status_counts[status] += 1
        context["status_counts"] = status_counts
        
        # Get pending question IDs (questions with status 'submitted' or 'resubmitted' that user can act on)
        pending_questions = [
            q for q in question_rows 
            if q.get('status') in ['submitted', 'resubmitted'] and q.get('can_act', False)
        ]
        pending_question_ids = [q['question_id'] for q in pending_questions]
        
        # Check if user can act on the assignment (any pending question they can act on)
        can_act = any(q.get('can_act', False) for q in question_rows)
        
        context["pending_question_ids"] = pending_question_ids
        context["pending_questions_count"] = len(pending_question_ids)
        context["can_act"] = can_act
        
        context["approval_dashboard_url"] = reverse("brsr:approval_dashboard")
        return context

    def _group_questions(self, questions):
        """Group questions by sub_section or section."""
        groups = {}
        for question in questions:
            key = question.get("sub_section") or "Questions"
            if key not in groups:
                groups[key] = {
                    "label": key,
                    "questions": []
                }
            groups[key]["questions"].append(question)
        
        # If only one group and it's the default "Questions", rename it
        if len(groups) == 1 and "Questions" in groups:
            return [{"label": "Submitted Responses", "questions": groups["Questions"]["questions"]}]
        
        return list(groups.values())

    def _can_act_on_question(self, assignment, response, user):
        """Check if user can act on this question."""
        if not user or not user.is_authenticated:
            return False
        if not assignment or not assignment.workflow_task:
            return False

        task = assignment.workflow_task
        if task.is_completed:
            return False

        stage_type = assignment.workflow_stage_type or (task.current_stage.stage_type if task.current_stage_id else "")
        if stage_type not in {"approval", "pre_final_approval", "final_approval"}:
            return False

        if response and response.status in {"approved", "rejected"}:
            return False

        task_info = _serialize_task_for_user(task, user)
        return bool(task_info and task_info.get("can_act"))


class AssignmentReviewCommentView(LoginRequiredMixin, TemplateView):
    login_url = "accounts:login"
    template_name = "brsr/assignment_review_comments.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        assignment_id = kwargs.get("assignment_id")
        user = self.request.user

        assignment = get_object_or_404(
            _my_dashboard_assignment_queryset(user).select_related(
                "plant",
                "section",
                "principle",
                "workflow_template",
                "assignee_content_type",
                "assigner_content_type",
            ).prefetch_related(
                "questions",
                "questions__section",
                "questions__principle",
                "responses",
                "responses__question",
            ),
            pk=assignment_id,
        )
        _ensure_assignment_workflow_task(assignment, current_user=user)

        questions = list(
            assignment.questions.select_related("section", "principle").order_by("display_order", "question_number")
        )
        responses = {response.question_id: response for response in assignment.responses.select_related("question")}

        task = assignment.workflow_task

        current_stage_type = (
            task.current_stage.stage_type
            if task and task.current_stage
            else ""
        )

        can_review = (
            _is_assigned_reviewer(user, assignment)
            and current_stage_type == "review"
        )
        question_rows = []
        for question in questions:
            response = responses.get(question.id)
            documents = []
            if response:
                documents = [
                    {
                        "id": doc.id,
                        "name": doc.original_name,
                        "url": doc.document.url,
                    }
                    for doc in response.documents.all()
                ]
            question_rows.append(
                {
                    "question_id": question.question_id,
                    "title": question.question_text,
                    "number": question.question_number,
                    "question_type": question.question_type,
                    "options": question.options or [],
                    "validation_rules": question.validation_rules or {},
                    "response_value": response.response_value if response else "",
                    "response_json": response.response_json if response else {},
                    "review_remark": response.review_remark if response else "",
                    "submitted_by": str(response.submitted_by) if response and response.submitted_by else "",
                    "submitted_at": response.submitted_at if response else None,
                    "can_edit_comment": can_review,
                    "reviewed_by": str(response.reviewed_by) if response and response.reviewed_by else "",
                    "reviewed_at": response.reviewed_at if response else None,
                    "documents": documents,
                }
            )

        context["assignment"] = _serialize_assignment(assignment, user)
        context["questions"] = question_rows
        context["questions_json"] = [
            {
                "question_id": q["question_id"],
                "question_type": q["question_type"],
                "options": q["options"],
                "validation_rules": q["validation_rules"],
                "response_value": q["response_value"],
                "response_json": q["response_json"],
            }
            for q in question_rows
        ]

        context["approval_dashboard_url"] = reverse("brsr:approval_dashboard")
        context["assignment_detail_url"] = reverse("brsr:assignment_detail", kwargs={"assignment_id": assignment.id})
        context["question_comment_api_url"] = reverse("brsr:question_comment_api", kwargs={"question_id": "__question__"})
        context["assignment_approve_api_url"] = reverse("brsr:assignment_approve_api", kwargs={"assignment_id": assignment.id})
        context["assignment_reject_api_url"] = reverse("brsr:assignment_reject_api", kwargs={"assignment_id": assignment.id})
        context["is_review_stage"] = assignment.workflow_stage_type == "review"
        context["is_assigned_reviewer"] = _is_assigned_reviewer(user, assignment)
        context["workflow_task"] = _serialize_workflow_task(assignment.workflow_task)
        return context

class BRSRQuestionWorkspaceView(LoginRequiredMixin, TemplateView):
    login_url = "accounts:login"
    template_name = "brsr/brsr_question_workspace.html"

    def _build_context(self, section_code=None, principle_slug=None, question_id=None, assignment_id=None):
        section, principle = _get_section_principle(section_code, principle_slug)
        if not section:
            section = _get_default_section()
        if not section:
            return {"section": None, "principle": None, "questions": [], "topics": []}

        assignment = None
        if assignment_id:
            assignment = (
                Assignment.objects.select_related("plant", "section", "principle", "workflow_template")
                .prefetch_related("questions", "questions__section", "questions__principle", "responses", "responses__documents")
                .filter(pk=assignment_id)
                .first()
            )

        if assignment:
            _ensure_assignment_workflow_task(assignment, current_user=self.request.user)
            questions = list(
                assignment.questions.filter(section=section).select_related("section", "principle", "parent_question").order_by("display_order", "question_number")
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

        topics = []
        for question in questions:
            topics.append(
                {
                    "question_id": question.question_id,
                    "title": question.question_text,
                    "question_type": question.question_type,
                    "status": _question_status(question, assignment=assignment),
                    "section_code": question.section.code,
                    "question_number": question.question_number,
                    "help_text": question.help_text or "",
                    "is_required": question.is_required,
                    "display_order": question.display_order,
                    "sub_section": question.sub_section or "",
                    **_question_metadata(question),
                }
            )

        active_question_payload = None
        if active_question:
            response_qs = QuestionResponse.objects.filter(question=active_question)
            if assignment:
                response_qs = response_qs.filter(assignment=assignment)
            response = (response_qs.select_related("assignment").prefetch_related("documents").order_by("-updated_at", "-created_at").first())
            task = assignment.workflow_task if assignment and assignment.workflow_task else (response.workflow_task if response else None)
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
            active_question_payload = {
                "question_id": active_question.question_id,
                "title": active_question.question_text,
                "question_type": active_question.question_type,
                "question_number": active_question.question_number,
                "sub_section": active_question.sub_section or "",
                "help_text": active_question.help_text or "",
                "placeholder_text": active_question.placeholder_text or "",
                "options": active_question.options or [],
                "documents": documents,
                "validation_rules": active_question.validation_rules or {},
                **_question_metadata(active_question),
                "status": response.status if response else "draft",
                "response_json": response.response_json if response else {},
                "response_value": response.response_value if response else "",
                "is_editable": (
                    (response.is_editable if response else True)
                    and (assignment.is_editable if assignment else True)
                ),
                "assignment_id": response.assignment.assignment_id if response else "",
                "workflow_stage": task.current_stage.label if task and task.current_stage_id else "",
                "workflow_stage_type": task.current_stage.stage_type if task and task.current_stage_id else "",
                "workflow_task": _serialize_workflow_task(task) if task else None,
            }

        section_cards = []
        for sec in _section_scope_queryset():
            section_cards.append(
                    {
                        "code": sec.code,
                        "name": sec.name,
                        "url": reverse("brsr:question_workspace_section", kwargs={"section_code": sec.code}),
                    }
                )

        principle_cards = []
        if section and section.code == "section_c":
            for principle_item in _principle_queryset():
                principle_cards.append(
                    {
                        "slug": principle_item.slug,
                        "name": principle_item.principle_name,
                        "title": principle_item.title,
                        "url": reverse(
                            "brsr:question_workspace_principle",
                            kwargs={"section_code": "section_c", "principle_slug": principle_item.slug},
                        ),
                    }
                )

        question_queryset = BRSRQuestion.objects.filter(id__in=[q.id for q in questions])
        assignment_bundle = _assignment_context(section, principle, question_queryset, assignment=assignment, user=self.request.user)

        section_locked = False
        if assignment and assignment.plant_id and assignment.financial_year:
            section_locked = _is_section_locked_for_new_assignment(
                self.request.user, assignment.plant, section, principle, assignment.financial_year
            )

        return {
            "section": section,
            "principle": principle,
            "assignment": assignment,
            "topics": topics,
            "active_question": active_question_payload,
            "active_question_id": active_question.question_id if active_question else "",
            "active_question_type": active_question.question_type if active_question else "",
            "section_cards": section_cards,
            "principle_cards": principle_cards,
            "counts": _workflow_counts(questions, assignment=assignment),
            "section_locked": section_locked,
            **assignment_bundle,
        }

    def get(self, request, section_code=None, principle_slug=None, question_id=None):
        assignment_id = request.GET.get("assignment_id")
        context = self._build_context(section_code, principle_slug, question_id, assignment_id=assignment_id)
        if not context.get("section"):
            messages.info(request, "No active BRSR section found.")
        context["workspace_api_url"] = reverse("brsr:workspace_api")
        context["question_detail_api_url"] = reverse("brsr:question_detail_api", kwargs={"question_id": "__question__"})
        context["question_save_api_url"] = reverse("brsr:question_save_api", kwargs={"question_id": "__question__"})
        context["question_submit_api_url"] = reverse("brsr:question_submit_api", kwargs={"question_id": "__question__"})
        context["question_comment_api_url"] = reverse("brsr:question_comment_api", kwargs={"question_id": "__question__"})
        context["question_approve_api_url"] = reverse("brsr:question_approve_api", kwargs={"question_id": "__question__"})
        context["question_reject_api_url"] = reverse("brsr:question_reject_api", kwargs={"question_id": "__question__"})
        context["assignment_create_api_url"] = reverse("brsr:assignment_create_api")
        context["assignment_options_api_url"] = reverse("brsr:assignment_options_api")
        context["assignment_dashboard_url"] = reverse("brsr:assignment_dashboard")
        context["assignment_id"] = assignment_id or ""
        context["current_section_code"] = section_code if section_code else (context["section"].code if context.get("section") else "")
        context["current_principle_slug"] = principle_slug if principle_slug else (context["principle"].slug if context.get("principle") else "")
        return render(request, self.template_name, context)

    def post(self, request, section_code=None, principle_slug=None, question_id=None):
        assignment_id = request.GET.get("assignment_id")
        context = self._build_context(section_code, principle_slug, question_id, assignment_id=assignment_id)
        active_questions = _pdf_questions_queryset().filter(section=context["section"])
        if context["principle"]:
            active_questions = active_questions.filter(principle=context["principle"])
        else:
            active_questions = active_questions.filter(principle__isnull=True)

        form = BRSRAssignmentForm(
            request.POST,
            plant_queryset=_company_scope_plants(self.request.user),
            user_queryset=User.objects.filter(is_active=True).select_related("role", "department").order_by(
                "full_name", "username"
            ),
            question_queryset=active_questions,
            financial_year_queryset=FinancialYear.objects.all().order_by("-start_date"),
        )
        if form.is_valid():
            selected_questions = form.cleaned_data["question_ids"]
            try:
                assignment, schedule = create_assignment_and_optional_schedule(
                    user=self.request.user,
                    section=context["section"],
                    principle=context["principle"],
                    cleaned_data=form.cleaned_data,
                    question_queryset=selected_questions,
                )
            except ValueError as exc:
                form.add_error(None, str(exc))
                context.update(
                    {
                        "workspace_api_url": reverse("brsr:workspace_api"),
                        "question_detail_api_url": reverse("brsr:question_detail_api", kwargs={"question_id": "__question__"}),
                        "question_save_api_url": reverse("brsr:question_save_api", kwargs={"question_id": "__question__"}),
                        "question_submit_api_url": reverse("brsr:question_submit_api", kwargs={"question_id": "__question__"}),
                        "question_comment_api_url": reverse("brsr:question_comment_api", kwargs={"question_id": "__question__"}),
                        "question_approve_api_url": reverse("brsr:question_approve_api", kwargs={"question_id": "__question__"}),
                        "question_reject_api_url": reverse("brsr:question_reject_api", kwargs={"question_id": "__question__"}),
                        "assignment_create_api_url": reverse("brsr:assignment_create_api"),
                        "assignment_options_api_url": reverse("brsr:assignment_options_api"),
                        "assignment_dashboard_url": reverse("brsr:assignment_dashboard"),
                        "assignment_form": form,
                        "current_section_code": section_code if section_code else (context["section"].code if context.get("section") else ""),
                        "current_principle_slug": principle_slug if principle_slug else (context["principle"].slug if context.get("principle") else ""),
                    }
                )
                return render(request, self.template_name, context)
            messages.success(
                request,
                f"Assignment {assignment.assignment_id} created for {selected_questions.count()} questions."
                + (f" Recurring schedule {schedule.schedule_id} set up." if schedule else ""),
            )
            return redirect(
                reverse(
                    "brsr:question_workspace_section",
                    kwargs={"section_code": context["section"].code},
                )
            )

        context.update(
            {
                "workspace_api_url": reverse("brsr:workspace_api"),
                "question_detail_api_url": reverse("brsr:question_detail_api", kwargs={"question_id": "__question__"}),
                "question_save_api_url": reverse("brsr:question_save_api", kwargs={"question_id": "__question__"}),
                "question_submit_api_url": reverse("brsr:question_submit_api", kwargs={"question_id": "__question__"}),
                "question_comment_api_url": reverse("brsr:question_comment_api", kwargs={"question_id": "__question__"}),
                "question_approve_api_url": reverse("brsr:question_approve_api", kwargs={"question_id": "__question__"}),
                "question_reject_api_url": reverse("brsr:question_reject_api", kwargs={"question_id": "__question__"}),
                "assignment_create_api_url": reverse("brsr:assignment_create_api"),
                "assignment_options_api_url": reverse("brsr:assignment_options_api"),
                "assignment_dashboard_url": reverse("brsr:assignment_dashboard"),
                "assignment_form": form,
                "current_section_code": section_code if section_code else (context["section"].code if context.get("section") else ""),
                "current_principle_slug": principle_slug if principle_slug else (context["principle"].slug if context.get("principle") else ""),
            }
        )
        return render(request, self.template_name, context)

class BRSRDataDashboardView(LoginRequiredMixin, TemplateView):
    login_url = "accounts:login"
    template_name = "brsr/brsr_data_dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        has_view_all = _user_has_permission(user, 'VIEW_ALL_BRSR_DATA')
        plants = list(_dashboard_plant_queryset(user))

        plant_cards = [
            {
                "plant": plant,
                "stats": _plant_brsr_stats(plant),
                "url": reverse("brsr:brsr_plant_data", kwargs={"plant_id": plant.id}),
            }
            for plant in plants
        ]

        context["plant_cards"] = plant_cards
        context["has_view_all"] = has_view_all
        if _is_admin_scope(user) and plants:
            context["company_stats"] = _company_brsr_stats(plants)
            context["company_url"] = reverse("brsr:brsr_company_data")
        return context


class BRSRPlantDataView(LoginRequiredMixin, TemplateView):
    login_url = "accounts:login"
    template_name = "brsr/brsr_entered_data.html"

    def get(self, request, *args, **kwargs):
        plant = get_object_or_404(
            Plant.objects.select_related("created_by__company"),
            pk=kwargs["plant_id"],
            is_active=True,
        )
        if not _can_view_plant_brsr_data(request.user, plant):
            messages.error(request, "You do not have permission to view this plant's BRSR data.")
            return redirect("brsr:brsr_data_dashboard")
        self.plant = plant
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        plant = self.plant

        financial_years = list(
            Assignment.objects.filter(plant=plant)
            .order_by("-financial_year")
            .values_list("financial_year", flat=True)
            .distinct()
        )
        selected_fy = self.request.GET.get("financial_year", "")
        if selected_fy and selected_fy not in financial_years:
            selected_fy = ""

        context.update({
            "is_company_view": False,
            "plant": plant,
            "financial_years": financial_years,
            "selected_fy": selected_fy,
            "section_groups": _build_brsr_data_groups([plant], financial_year=selected_fy or None),
            "sections_nav": [{"code": g["section"].code, "name": g["section"].name} for g in _build_brsr_data_groups([plant], financial_year=selected_fy or None)],
            "stats": _plant_brsr_stats(plant, financial_year=selected_fy or None),
            "dashboard_url": reverse("brsr:brsr_data_dashboard"),
            "page_title": f"{plant.name} — Entered BRSR Data",
        })
        return context


class BRSRCompanyDataView(LoginRequiredMixin, TemplateView):
    login_url = "accounts:login"
    template_name = "brsr/brsr_entered_data.html"

    def get(self, request, *args, **kwargs):
        user = request.user
        if not _is_admin_scope(user):
            messages.error(request, "You do not have permission to view company-wide BRSR data.")
            return redirect("brsr:brsr_data_dashboard")
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        plants = list(_dashboard_plant_queryset(user))

        financial_years = list(
            Assignment.objects.filter(plant__in=plants)
            .order_by("-financial_year")
            .values_list("financial_year", flat=True)
            .distinct()
        )
        selected_fy = self.request.GET.get("financial_year", "")
        if selected_fy and selected_fy not in financial_years:
            selected_fy = ""

        company = getattr(getattr(plants[0], "created_by", None), "company", None) if plants else None

        context.update({
            "is_company_view": True,
            "plant": None,
            "company_name": company.company_name if company else "All Plants",
            "financial_years": financial_years,
            "selected_fy": selected_fy,
            "section_groups": _build_brsr_data_groups(plants, financial_year=selected_fy or None),
            "stats": _company_brsr_stats(plants, financial_year=selected_fy or None),
            "dashboard_url": reverse("brsr:brsr_data_dashboard"),
            "page_title": "Company-wide BRSR Data",
        })
        return context

def brsr_list(request):
    return BRSRDashboardView.as_view()(request)


def brsr_workspace(request, section_code=None, principle_slug=None, question_id=None):
    return BRSRQuestionWorkspaceView.as_view()(request, section_code=section_code, principle_slug=principle_slug, question_id=question_id)
