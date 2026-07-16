from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from rest_framework.test import APIRequestFactory, force_authenticate

from apps.accounts.models import Department
from apps.accounts.models.role import Role
from apps.accounts.models.user import User
from apps.brsr.api_views import QuestionApproveAPIView, QuestionRejectAPIView, QuestionReviewCommentAPIView, QuestionSaveAPIView, QuestionSubmitAPIView
from apps.brsr.models import Assignment, BRSRQuestion, BRSRSection, QuestionResponse
from apps.organizations.models import ApprovalConfigurationStage, ApprovalConfigurationTemplate, Plant
from apps.organizations.workflow_configuration_engine import WorkflowConfigurationEngine
from apps.companies.models import City, Company, Country, State


class BRSRWorkflowAPITests(TestCase):
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
        assignment.questions.add(self.question)
        QuestionResponse.objects.create(
            assignment=assignment,
            question=self.question,
            response_value=f"Initial draft {suffix}",
        )
        return assignment

    def test_data_entry_submit_advances_through_final_approval(self):
        assignment = self._create_assignment()

        request = self.factory.put(
            "/fake-save/",
            {
                "assignment_id": assignment.id,
                "response_value": "Draft response",
            },
            format="json",
        )
        force_authenticate(request, user=self.data_user)
        response = QuestionSaveAPIView.as_view()(request, question_id=self.question.question_id)
        self.assertEqual(response.status_code, 200)

        assignment.refresh_from_db()
        self.assertEqual(assignment.workflow_stage_type, "data_entry")
        self.assertEqual(assignment.workflow_task.current_assignee_object_id, self.data_user.id)

        request = self.factory.post(
            "/fake-submit/",
            {"assignment_id": assignment.id},
            format="json",
        )
        force_authenticate(request, user=self.data_user)
        response = QuestionSubmitAPIView.as_view()(request, question_id=self.question.question_id)
        self.assertEqual(response.status_code, 200)

        assignment.refresh_from_db()
        self.assertEqual(assignment.workflow_stage_type, "review")
        self.assertEqual(assignment.workflow_task.current_assignee_object_id, self.reviewer.id)

        request = self.factory.post(
            "/fake-approve/",
            {"assignment_id": assignment.id},
            format="json",
        )
        force_authenticate(request, user=self.reviewer)
        response = QuestionApproveAPIView.as_view()(request, question_id=self.question.question_id)
        self.assertEqual(response.status_code, 200)

        assignment.refresh_from_db()
        self.assertEqual(assignment.workflow_stage_type, "approval")
        self.assertEqual(assignment.workflow_task.current_assignee_object_id, self.approver.id)

        request = self.factory.post(
            "/fake-approve/",
            {"assignment_id": assignment.id},
            format="json",
        )
        force_authenticate(request, user=self.approver)
        response = QuestionApproveAPIView.as_view()(request, question_id=self.question.question_id)
        self.assertEqual(response.status_code, 200)

        assignment.refresh_from_db()
        self.assertEqual(assignment.workflow_stage_type, "pre_final_approval")
        self.assertEqual(assignment.workflow_task.current_assignee_object_id, self.head.id)

        request = self.factory.post(
            "/fake-approve/",
            {"assignment_id": assignment.id},
            format="json",
        )
        force_authenticate(request, user=self.head)
        response = QuestionApproveAPIView.as_view()(request, question_id=self.question.question_id)
        self.assertEqual(response.status_code, 200)

        assignment.refresh_from_db()
        self.assertEqual(assignment.workflow_stage_type, "final_approval")
        self.assertEqual(assignment.workflow_task.current_assignee_object_id, self.chair.id)

        request = self.factory.post(
            "/fake-approve/",
            {"assignment_id": assignment.id},
            format="json",
        )
        force_authenticate(request, user=self.chair)
        response = QuestionApproveAPIView.as_view()(request, question_id=self.question.question_id)
        self.assertEqual(response.status_code, 200)

        assignment.refresh_from_db()
        self.assertTrue(assignment.workflow_task.is_completed)

    def test_reject_returns_to_data_entry_user(self):
        assignment = self._create_assignment("2")

        request = self.factory.put(
            "/fake-save/",
            {"assignment_id": assignment.id, "response_value": "Draft response"},
            format="json",
        )
        force_authenticate(request, user=self.data_user)
        response = QuestionSaveAPIView.as_view()(request, question_id=self.question.question_id)
        self.assertEqual(response.status_code, 200)

        request = self.factory.post(
            "/fake-submit/",
            {"assignment_id": assignment.id},
            format="json",
        )
        force_authenticate(request, user=self.data_user)
        response = QuestionSubmitAPIView.as_view()(request, question_id=self.question.question_id)
        self.assertEqual(response.status_code, 200)

        request = self.factory.post(
            "/fake-reject/",
            {"assignment_id": assignment.id, "remark": "Need fixes"},
            format="json",
        )
        force_authenticate(request, user=self.reviewer)
        response = QuestionRejectAPIView.as_view()(request, question_id=self.question.question_id)
        self.assertEqual(response.status_code, 200)

        assignment.refresh_from_db()
        self.assertEqual(assignment.workflow_stage_type, "data_entry")
        self.assertEqual(assignment.workflow_task.current_assignee_object_id, self.data_user.id)
        self.assertTrue(assignment.workflow_task.is_returned)

    def test_review_comment_can_be_saved_during_review_stage(self):
        assignment = self._create_assignment("3")

        request = self.factory.put(
            "/fake-save/",
            {"assignment_id": assignment.id, "response_value": "Draft response"},
            format="json",
        )
        force_authenticate(request, user=self.data_user)
        response = QuestionSaveAPIView.as_view()(request, question_id=self.question.question_id)
        self.assertEqual(response.status_code, 200)

        request = self.factory.post(
            "/fake-submit/",
            {"assignment_id": assignment.id},
            format="json",
        )
        force_authenticate(request, user=self.data_user)
        response = QuestionSubmitAPIView.as_view()(request, question_id=self.question.question_id)
        self.assertEqual(response.status_code, 200)

        request = self.factory.post(
            "/fake-comment/",
            {"assignment_id": assignment.id, "remark": "Looks good"},
            format="json",
        )
        force_authenticate(request, user=self.reviewer)
        response = QuestionReviewCommentAPIView.as_view()(request, question_id=self.question.question_id)
        self.assertEqual(response.status_code, 200)

        response_row = QuestionResponse.objects.get(assignment=assignment, question=self.question)
        self.assertEqual(response_row.review_remark, "Looks good")
        self.assertEqual(response_row.status, "submitted")

    def test_final_approval_locks_editing_after_approval(self):
        assignment = self._create_assignment("4")

        request = self.factory.put(
            "/fake-save/",
            {"assignment_id": assignment.id, "response_value": "Draft response"},
            format="json",
        )
        force_authenticate(request, user=self.data_user)
        response = QuestionSaveAPIView.as_view()(request, question_id=self.question.question_id)
        self.assertEqual(response.status_code, 200)

        request = self.factory.post(
            "/fake-submit/",
            {"assignment_id": assignment.id},
            format="json",
        )
        force_authenticate(request, user=self.data_user)
        response = QuestionSubmitAPIView.as_view()(request, question_id=self.question.question_id)
        self.assertEqual(response.status_code, 200)

        for user in [self.reviewer, self.approver, self.head]:
            request = self.factory.post(
                "/fake-approve/",
                {"assignment_id": assignment.id},
                format="json",
            )
            force_authenticate(request, user=user)
            response = QuestionApproveAPIView.as_view()(request, question_id=self.question.question_id)
            self.assertEqual(response.status_code, 200)

        request = self.factory.post(
            "/fake-approve/",
            {"assignment_id": assignment.id},
            format="json",
        )
        force_authenticate(request, user=self.chair)
        response = QuestionApproveAPIView.as_view()(request, question_id=self.question.question_id)
        self.assertEqual(response.status_code, 200)

        assignment.refresh_from_db()
        response_row = QuestionResponse.objects.get(assignment=assignment, question=self.question)
        self.assertEqual(assignment.workflow_stage_type, "final_approval")
        self.assertTrue(assignment.workflow_task.is_completed)
        self.assertFalse(response_row.is_editable)
        self.assertEqual(response_row.status, "approved")

        request = self.factory.put(
            "/fake-save/",
            {"assignment_id": assignment.id, "response_value": "Edited after approval"},
            format="json",
        )
        force_authenticate(request, user=self.chair)
        response = QuestionSaveAPIView.as_view()(request, question_id=self.question.question_id)
        self.assertEqual(response.status_code, 409)
