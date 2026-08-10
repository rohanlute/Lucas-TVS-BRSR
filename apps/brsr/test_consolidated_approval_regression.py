from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from rest_framework.test import APIRequestFactory, force_authenticate

from apps.accounts.models import Department
from apps.accounts.models.role import Role
from apps.accounts.models.user import User
from apps.brsr.api_views import (
    QuestionApproveAPIView,
    QuestionReviewCommentAPIView,
    QuestionSaveAPIView,
    QuestionSubmitAPIView,
    AssignmentFinalizeReviewAPIView,
)
from apps.brsr.models import Assignment, AssignmentReviewer, BRSRQuestion, BRSRSection, QuestionResponse
from apps.brsr.views import (
    _approval_stage_queryset,
    _is_assignment_ready_for_pre_final,
    _section_principle_ready_for_pre_final,
)
from apps.companies.models import City, Company, Country, State
from apps.organizations.models import ApprovalConfigurationStage, ApprovalConfigurationTemplate, Plant


class ConsolidatedApprovalRegressionTests(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.country = Country.objects.create(name="India", iso_code="IN")
        self.state = State.objects.create(country=self.country, name="Tamil Nadu", state_code="TN")
        self.city = City.objects.create(country=self.country, state=self.state, name="Chennai")

        self.company = Company.objects.create(
            company_code="LUCAS",
            company_name="Lucas TVS",
            contact_person="Admin",
            email="admin@lucastvs.com",
            mobile_number="9999999999",
            billing_country=self.country,
            billing_state=self.state,
            billing_city=self.city,
        )

        self.department = Department.objects.create(name="ESG", code="ESG")

        self.question_assignment_role = Role.objects.create(role_code="ESG-COORD", role_name="ESG Coordinator")
        self.data_entry_role = Role.objects.create(role_code="DEPT-USER", role_name="Department User")
        self.review_role = Role.objects.create(role_code="DEPT-APPR", role_name="Department Approver")
        self.approval_role = Role.objects.create(role_code="ESG-APPROVER", role_name="ESG Coordinator Approver")
        self.pre_final_role = Role.objects.create(role_code="ESG-HEAD", role_name="ESG Head")
        self.final_role = Role.objects.create(role_code="ESG-CHAIR", role_name="ESG Chairperson")

        self.assigner = self._make_user("assigner", self.question_assignment_role, "ESG Coordinator")
        self.data_user = self._make_user("data_user", self.data_entry_role, "Department User")
        self.reviewer = self._make_user("reviewer", self.review_role, "Department Approver")
        self.approver = self._make_user("approver", self.approval_role, "ESG Coordinator Approver")
        self.head = self._make_user("head", self.pre_final_role, "ESG Head")
        self.chair = self._make_user("chair", self.final_role, "ESG Chairperson")

        self.plant = Plant.objects.create(
            name="Lucas Plant",
            code="LUCAS-01",
            address="Plant Address",
            pincode="600001",
            created_by=self.assigner,
        )
        for user in [self.assigner, self.data_user, self.reviewer, self.approver, self.head, self.chair]:
            user.assigned_plants.add(self.plant)

        self.template = ApprovalConfigurationTemplate.objects.create(
            company=self.company,
            framework="BRSR",
            name="Lucas TVS Work Flow",
        )
        ApprovalConfigurationStage.objects.create(
            template=self.template,
            level=1,
            label="L1 - Assign",
            stage_type="question_assignment",
            role=self.question_assignment_role,
        )
        ApprovalConfigurationStage.objects.create(
            template=self.template,
            level=2,
            label="L2 - Data Entry",
            stage_type="data_entry",
            role=self.data_entry_role,
        )
        ApprovalConfigurationStage.objects.create(
            template=self.template,
            level=3,
            label="L3 - Review",
            stage_type="review",
            role=self.review_role,
        )
        ApprovalConfigurationStage.objects.create(
            template=self.template,
            level=4,
            label="L4 - Approval",
            stage_type="approval",
            role=self.approval_role,
        )
        ApprovalConfigurationStage.objects.create(
            template=self.template,
            level=5,
            label="L5 - Pre Final Approval",
            stage_type="pre_final_approval",
            role=self.pre_final_role,
        )
        ApprovalConfigurationStage.objects.create(
            template=self.template,
            level=6,
            label="L6 - Final Approval",
            stage_type="final_approval",
            role=self.final_role,
        )

        self.section = BRSRSection.objects.create(code="section_a", name="General Disclosures", display_order=1)
        self.question = BRSRQuestion.objects.create(
            question_id="a_q1",
            section=self.section,
            question_text="Test question?",
            question_number="1",
            question_type="text",
            display_order=1,
        )

    def _make_user(self, username, role, full_name):
        user = User.objects.create_user(
            username=username,
            password="pass12345",
            full_name=full_name,
            email=f"{username}@example.com",
            company=self.company,
            department=self.department,
            role=role,
            is_active=True,
        )
        return user

    def _create_assignment(self, suffix="1"):
        assignment = Assignment.objects.create(
            plant=self.plant,
            section=self.section,
            financial_year="2025-2026",
            workflow_template=self.template,
            assigner_content_type=ContentType.objects.get_for_model(User),
            assigner_object_id=self.assigner.id,
            assignee_content_type=ContentType.objects.get_for_model(User),
            assignee_object_id=self.data_user.id,
        )
        AssignmentReviewer.objects.create(
            assignment=assignment,
            reviewer_content_type=ContentType.objects.get_for_model(User),
            reviewer_object_id=self.reviewer.id,
        )
        assignment.questions.add(self.question)
        QuestionResponse.objects.create(
            assignment=assignment,
            question=self.question,
            response_value=f"Initial draft {suffix}",
        )
        return assignment

    def _submit_assignment(self, assignment):
        save_request = self.factory.put(
            "/fake-save/",
            {"assignment_id": assignment.id, "response_value": "Draft response"},
            format="json",
        )
        force_authenticate(save_request, user=self.data_user)
        QuestionSaveAPIView.as_view()(save_request, question_id=self.question.question_id)

        submit_request = self.factory.post(
            "/fake-submit/",
            {"assignment_id": assignment.id},
            format="json",
        )
        force_authenticate(submit_request, user=self.data_user)
        response = QuestionSubmitAPIView.as_view()(submit_request, question_id=self.question.question_id)
        self.assertEqual(response.status_code, 200)
        assignment.refresh_from_db()
        self.assertEqual(assignment.workflow_stage_type, "review")

    def _review_assignment_to_approval(self, assignment):
        review_request = self.factory.post(
            "/fake-comment/",
            {"assignment_id": assignment.id, "remark": "Looks good"},
            format="json",
        )
        force_authenticate(review_request, user=self.reviewer)
        response = QuestionReviewCommentAPIView.as_view()(review_request, question_id=self.question.question_id)
        self.assertEqual(response.status_code, 200)

        finalize_request = self.factory.post(
            "/fake-finalize/",
            {"assignment_id": assignment.id},
            format="json",
        )
        force_authenticate(finalize_request, user=self.reviewer)
        response = AssignmentFinalizeReviewAPIView.as_view()(finalize_request, assignment_id=assignment.id)
        self.assertEqual(response.status_code, 200)

        assignment.refresh_from_db()
        self.assertEqual(assignment.workflow_stage_type, "approval")

    def _approve_assignment_to_pre_final(self, assignment):
        approve_request = self.factory.post(
            "/fake-approve/",
            {"assignment_id": assignment.id},
            format="json",
        )
        force_authenticate(approve_request, user=self.approver)
        response = QuestionApproveAPIView.as_view()(approve_request, question_id=self.question.question_id)
        self.assertEqual(response.status_code, 200)
        assignment.refresh_from_db()
        self.assertEqual(assignment.workflow_stage_type, "pre_final_approval")
        assignment.assignment_status = "approved"
        assignment.save(update_fields=["assignment_status", "updated_at"])

    def test_only_role_matching_user_can_see_stage_in_approval_dashboard(self):
        approval_assignment = self._create_assignment("approval")
        pre_final_assignment = self._create_assignment("pre-final")

        self._submit_assignment(approval_assignment)
        self._review_assignment_to_approval(approval_assignment)

        self._submit_assignment(pre_final_assignment)
        self._review_assignment_to_approval(pre_final_assignment)
        self._approve_assignment_to_pre_final(pre_final_assignment)

        visible_for_head = _approval_stage_queryset(self.head)
        visible_for_approver = _approval_stage_queryset(self.approver)

        self.assertEqual(len(visible_for_head), 1)
        self.assertEqual(visible_for_head[0].id, pre_final_assignment.id)

        self.assertEqual(len(visible_for_approver), 1)
        self.assertEqual(visible_for_approver[0].id, approval_assignment.id)

    def test_pre_final_ready_gate_accepts_assignments_at_approval_before_section_send(self):
        assignment = self._create_assignment("ready")
        self._submit_assignment(assignment)
        self._review_assignment_to_approval(assignment)

        ready, count = _section_principle_ready_for_pre_final(
            self.head,
            self.plant,
            self.section,
            None,
            "2025-2026",
        )
        self.assertTrue(ready)
        self.assertEqual(count, 1)

        self._approve_assignment_to_pre_final(assignment)
        ready, count = _section_principle_ready_for_pre_final(
            self.head,
            self.plant,
            self.section,
            None,
            "2025-2026",
        )
        self.assertFalse(ready)
        self.assertEqual(count, 1)

    def test_assignment_is_ready_for_pre_final_only_when_current_stage_is_approval(self):
        assignment = self._create_assignment("gate")
        self._submit_assignment(assignment)
        self._review_assignment_to_approval(assignment)
        self.assertTrue(_is_assignment_ready_for_pre_final(assignment))

        self._approve_assignment_to_pre_final(assignment)
        self.assertFalse(_is_assignment_ready_for_pre_final(assignment))
