from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.contenttypes.models import ContentType
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.generic import TemplateView
from apps.accounts.models import Department
from apps.organizations.models import FinancialYear, Plant
from .forms import BRSRAssignmentForm
from .models import Assignment, BRSRPrinciple, BRSRQuestion, BRSRSection, QuestionResponse


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

def _get_section_principle(section_code=None, principle_slug=None):
    section = None
    principle = None

    if section_code:
        section = get_object_or_404(BRSRSection, code=section_code, is_active=True)
    else:
        section = _get_default_section()

    if section and section.code == "section_c":
        principles = _principle_queryset()
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


def _question_status(question):
    response = (
        QuestionResponse.objects.filter(question=question)
        .select_related("assignment")
        .order_by("-updated_at", "-created_at")
        .first()
    )
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


def _workflow_counts(questions):
    question_ids = [q.id for q in questions]
    responses = QuestionResponse.objects.filter(question_id__in=question_ids)
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


def _serialize_assignment(assignment):
    questions = list(assignment.questions.select_related("section", "principle").order_by("display_order", "question_number"))
    first_question = questions[0] if questions else None
    response_map = {
        response.question_id: response.status
        for response in assignment.responses.all().only("question_id", "status")
    }
    return {
        "id": assignment.id,
        "assignment_id": assignment.assignment_id,
        "plant": assignment.plant.name if assignment.plant_id else "",
        "plant_code": assignment.plant.code if assignment.plant_id else "",
        "assignee": _actor_label(assignment.assignee),
        "assignee_type": assignment.assignee_content_type.model if assignment.assignee_content_type_id else "",
        "assigner": _actor_label(assignment.assigner),
        "section": assignment.section.name if assignment.section_id else "",
        "section_code": assignment.section.code if assignment.section_id else "",
        "principle": assignment.principle.principle_name if assignment.principle_id else "",
        "financial_year": assignment.financial_year,
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
        ),
    }


def _assignment_context(section, principle, questions):
    latest_assignment = (
        Assignment.objects.filter(section=section, principle=principle)
        .select_related("plant")
        .order_by("-created_at")
        .first()
    )
    plant_qs = Plant.objects.filter(is_active=True).order_by("name")
    user_qs = User.objects.filter(is_active=True).select_related("role", "department").order_by(
        "full_name", "username"
    )
    fy_qs = FinancialYear.objects.all().order_by("-start_date")
    # Parent assignment / delegation removed from workflow
    return {
        "latest_assignment": latest_assignment,
        "assignment_form": BRSRAssignmentForm(
            plant_queryset=plant_qs,
            user_queryset=user_qs,
            question_queryset=questions,
            financial_year_queryset=fy_qs,
        ),
        "plants": plant_qs,
        "users": user_qs,
        "financial_years": fy_qs,
    }


class BRSRDashboardView(LoginRequiredMixin, TemplateView):
    login_url = "accounts:login"
    template_name = "brsr/brsr_list.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        sections = _section_scope_queryset()
        principles = _principle_queryset()

        section_cards = []
        for section in sections:
            question_count = _question_queryset(section).count()
            section_cards.append(
                {
                    "section": section,
                    "question_count": question_count,
                    "url": reverse("brsr:question_workspace_section", kwargs={"section_code": section.code}),
                }
            )

        principle_cards = []
        for principle in principles:
            principle_cards.append(
                {
                    "principle": principle,
                    "question_count": principle.questions.filter(is_active=True).count(),
                    "url": reverse(
                        "brsr:question_workspace_principle",
                        kwargs={"section_code": "section_c", "principle_slug": principle.slug},
                    ),
                }
            )

        context["section_cards"] = section_cards
        context["principle_cards"] = principle_cards
        context["workspace_url"] = reverse("brsr:question_workspace")
        context["total_questions"] = _pdf_questions_queryset().count()
        context["total_sections"] = sections.count()
        context["total_principles"] = principles.count()
        return context


class AssignmentDashboardView(LoginRequiredMixin, TemplateView):
    login_url = "accounts:login"
    template_name = "brsr/assignment_dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        assignments = (
            _assignment_scope_queryset(user)
            .select_related(
                "plant",
                "section",
                "principle",
                "assignee_content_type",
                "assigner_content_type",
            )
            .prefetch_related(
                "questions",
                "responses",
                "questions__section",
                "questions__principle",
            )
            .order_by("-created_at")
        )

        serialized_assignments = [_serialize_assignment(assignment) for assignment in assignments]
        context["assignments"] = serialized_assignments
        context["assignment_count"] = len(serialized_assignments)
        context["open_count"] = sum(1 for item in serialized_assignments if item["overall_status"] != "completed")
        context["completed_count"] = sum(1 for item in serialized_assignments if item["overall_status"] == "completed")
        context["overdue_count"] = sum(1 for item in serialized_assignments if item["is_overdue"])
        context["assignment_scope"] = _get_assignment_scope(user)
        return context


class BRSRQuestionWorkspaceView(LoginRequiredMixin, TemplateView):
    login_url = "accounts:login"
    template_name = "brsr/brsr_question_workspace.html"

    def _build_context(self, section_code=None, principle_slug=None, question_id=None):
        section, principle = _get_section_principle(section_code, principle_slug)
        if not section:
            section = _get_default_section()
        if not section:
            return {"section": None, "principle": None, "questions": [], "topics": []}

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
                    "status": _question_status(question),
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
            response = (
                QuestionResponse.objects.filter(question=active_question)
                .select_related("assignment")
                .order_by("-updated_at", "-created_at")
                .first()
            )
            active_question_payload = {
                "question_id": active_question.question_id,
                "title": active_question.question_text,
                "question_type": active_question.question_type,
                "question_number": active_question.question_number,
                "sub_section": active_question.sub_section or "",
                "help_text": active_question.help_text or "",
                "placeholder_text": active_question.placeholder_text or "",
                "options": active_question.options or [],
                "validation_rules": active_question.validation_rules or {},
                **_question_metadata(active_question),
                "status": response.status if response else "draft",
                "response_json": response.response_json if response else {},
                "response_value": response.response_value if response else "",
                "is_editable": response.is_editable if response else True,
                "assignment_id": response.assignment.assignment_id if response else "",
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
        assignment_bundle = _assignment_context(section, principle, question_queryset)

        return {
            "section": section,
            "principle": principle,
            "topics": topics,
            "active_question": active_question_payload,
            "active_question_id": active_question.question_id if active_question else "",
            "active_question_type": active_question.question_type if active_question else "",
            "section_cards": section_cards,
            "principle_cards": principle_cards,
            "counts": _workflow_counts(questions),
            **assignment_bundle,
        }

    def get(self, request, section_code=None, principle_slug=None, question_id=None):
        context = self._build_context(section_code, principle_slug, question_id)
        if not context.get("section"):
            messages.info(request, "No active BRSR section found.")
        context["workspace_api_url"] = reverse("brsr:workspace_api")
        context["question_detail_api_url"] = reverse("brsr:question_detail_api", kwargs={"question_id": "__question__"})
        context["question_save_api_url"] = reverse("brsr:question_save_api", kwargs={"question_id": "__question__"})
        context["question_submit_api_url"] = reverse("brsr:question_submit_api", kwargs={"question_id": "__question__"})
        context["assignment_create_api_url"] = reverse("brsr:assignment_create_api")
        context["assignment_options_api_url"] = reverse("brsr:assignment_options_api")
        context["assignment_dashboard_url"] = reverse("brsr:assignment_dashboard")
        context["current_section_code"] = section_code if section_code else (context["section"].code if context.get("section") else "")
        context["current_principle_slug"] = principle_slug if principle_slug else (context["principle"].slug if context.get("principle") else "")
        return render(request, self.template_name, context)

    def post(self, request, section_code=None, principle_slug=None, question_id=None):
        context = self._build_context(section_code, principle_slug, question_id)
        active_questions = _pdf_questions_queryset().filter(section=context["section"])
        if context["principle"]:
            active_questions = active_questions.filter(principle=context["principle"])
        else:
            active_questions = active_questions.filter(principle__isnull=True)

        form = BRSRAssignmentForm(
            request.POST,
            plant_queryset=Plant.objects.filter(is_active=True).order_by("name"),
            user_queryset=User.objects.filter(is_active=True).select_related("role", "department").order_by(
                "full_name", "username"
            ),
            question_queryset=active_questions,
            financial_year_queryset=FinancialYear.objects.all().order_by("-start_date"),
        )
        if form.is_valid():
            user_ct = ContentType.objects.get_for_model(User)
            assignment = Assignment.objects.create(
                plant=form.cleaned_data["plant"],
                principle=context["principle"],
                section=context["section"],
                financial_year=form.cleaned_data["financial_year"],
                # parent removed from creation flow
                data_collection_frequency=form.cleaned_data.get("data_collection_frequency") or "",
                assigner_content_type=user_ct,
                assigner_object_id=form.cleaned_data["assigner"].pk,
                assignee_content_type=user_ct,
                assignee_object_id=form.cleaned_data["assignee"].pk,
                due_date=form.cleaned_data.get("due_date"),
                priority=form.cleaned_data["priority"],
                notes=form.cleaned_data.get("notes"),
            )
            selected_questions = form.cleaned_data["question_ids"]
            assignment.questions.set(selected_questions)
            for question in selected_questions:
                QuestionResponse.objects.get_or_create(
                    assignment=assignment,
                    question=question,
                )
            messages.success(
                request,
                f"Assignment {assignment.assignment_id} created for {selected_questions.count()} questions.",
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
                "assignment_create_api_url": reverse("brsr:assignment_create_api"),
                "assignment_options_api_url": reverse("brsr:assignment_options_api"),
                "assignment_dashboard_url": reverse("brsr:assignment_dashboard"),
                "assignment_form": form,
                "current_section_code": section_code if section_code else (context["section"].code if context.get("section") else ""),
                "current_principle_slug": principle_slug if principle_slug else (context["principle"].slug if context.get("principle") else ""),
            }
        )
        return render(request, self.template_name, context)


def brsr_list(request):
    return BRSRDashboardView.as_view()(request)


def brsr_workspace(request, section_code=None, principle_slug=None, question_id=None):
    return BRSRQuestionWorkspaceView.as_view()(request, section_code=section_code, principle_slug=principle_slug, question_id=question_id)
