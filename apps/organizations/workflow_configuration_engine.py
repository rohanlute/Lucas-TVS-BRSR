"""
Workflow configuration engine for tenant-scoped, role-based workflow templates.
"""

from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.utils import timezone

from .models import ApprovalConfigurationTask, ApprovalConfigurationTaskLog


class WorkflowConfigurationEngine:
    @staticmethod
    def _user_role_matches(user, stage):
        return bool(stage and stage.role_id and getattr(user, "role_id", None) == stage.role_id)

    @staticmethod
    def _actor_ref(actor):
        if actor is None:
            return None, None
        actor_ct = ContentType.objects.get_for_model(actor.__class__)
        return actor_ct, getattr(actor, "pk", None)

    @classmethod
    def _move_to_stage(cls, task, user, next_stage, remark="", next_assignee=None, action="approve"):
        if task.is_completed:
            raise PermissionDenied("This workflow has already been completed.")
        actor_ct, actor_id = cls._actor_ref(user)
        next_assignee_ct = next_assignee_id = None
        if next_assignee is not None:
            next_assignee_ct, next_assignee_id = cls._actor_ref(next_assignee)
            if not next_assignee_ct or not next_assignee_id:
                raise ValueError("next_assignee must be a concrete model instance.")

        with transaction.atomic():
            ApprovalConfigurationTaskLog.objects.create(
                task=task,
                action=action,
                from_stage=task.current_stage,
                to_stage=next_stage,
                actor_content_type=actor_ct,
                actor_object_id=actor_id,
                remark=remark,
            )
            if next_stage is None:
                task.is_completed = True
                task.is_returned = False
            else:
                task.current_stage = next_stage
                task.is_returned = False
                if next_assignee is not None:
                    task.current_assignee_content_type = next_assignee_ct
                    task.current_assignee_object_id = next_assignee_id
            task.save()
            cls._sync_denormalized_status(task)
        return task

    @classmethod
    def start(cls, template, target, first_assignee):
        first_stage = template.stages.order_by("level").first()
        if not first_stage:
            raise ValueError("Workflow configuration template has no stages configured.")

        assignee_ct, assignee_id = cls._actor_ref(first_assignee)
        target_ct, target_id = cls._actor_ref(target)
        if not assignee_ct or not target_ct:
            raise ValueError("Target and assignee must be concrete model instances.")

        with transaction.atomic():
            task = ApprovalConfigurationTask.objects.create(
                template=template,
                current_stage=first_stage,
                target_content_type=target_ct,
                target_object_id=target_id,
                current_assignee_content_type=assignee_ct,
                current_assignee_object_id=assignee_id,
            )
            ApprovalConfigurationTaskLog.objects.create(
                task=task,
                action="submit",
                to_stage=first_stage,
                actor_content_type=assignee_ct,
                actor_object_id=assignee_id,
            )
        return task

    @classmethod
    def approve(cls, task, user, remark="", next_assignee=None):
        if task.is_completed:
            raise PermissionDenied("This workflow has already been completed.")
        stage = task.current_stage
        if not stage.can_approve:
            raise PermissionDenied("This stage cannot approve.")
        if not cls._user_role_matches(user, stage):
            raise PermissionDenied("User role does not match the required approver role for this stage.")

        next_stage = stage.next_stage()
        return cls._move_to_stage(task, user, next_stage, remark=remark, next_assignee=next_assignee, action="approve")

    @classmethod
    def advance_to_next_stage(cls, task, user, remark="", next_assignee=None):
        """
        Move a task to the next workflow stage without enforcing approver
        permissions. This is intended for automatic system transitions, such as
        skipping a question-assignment gate after the assignment is created.
        """
        if task.is_completed:
            raise PermissionDenied("This workflow has already been completed.")
        next_stage = task.current_stage.next_stage() if task.current_stage_id else None
        return cls._move_to_stage(task, user, next_stage, remark=remark, next_assignee=next_assignee, action="approve")

    @classmethod
    def advance_skipping_stage_types(cls, task, user, skip_stage_types=None, remark="", next_assignee=None):
        """
        Advance to the next non-skipped stage in a single hop.
        This is useful when a workflow contains an optional, comment-only stage
        that should not block progression, such as a reviewer note stage.
        """
        if task.is_completed:
            raise PermissionDenied("This workflow has already been completed.")
        skip_stage_types = set(skip_stage_types or [])
        next_stage = task.current_stage.next_stage() if task.current_stage_id else None
        while next_stage and next_stage.stage_type in skip_stage_types:
            next_stage = next_stage.next_stage()
        return cls._move_to_stage(task, user, next_stage, remark=remark, next_assignee=next_assignee, action="approve")

    @classmethod
    def reject(cls, task, user, remark, return_to_stage=None, return_to_assignee=None):
        if task.is_completed:
            raise PermissionDenied("This workflow has already been completed.")
        stage = task.current_stage
        if not stage.can_reject:
            raise PermissionDenied("This stage cannot reject.")
        if not cls._user_role_matches(user, stage):
            raise PermissionDenied("User role does not match the required reviewer role for this stage.")
        if not remark:
            raise ValueError("Rejection requires a remark.")

        target_stage = return_to_stage or stage.previous_stage() or stage
        actor_ct, actor_id = cls._actor_ref(user)
        with transaction.atomic():
            ApprovalConfigurationTaskLog.objects.create(
                task=task,
                action="reject",
                from_stage=stage,
                to_stage=target_stage,
                actor_content_type=actor_ct,
                actor_object_id=actor_id,
                remark=remark,
            )
            task.current_stage = target_stage
            task.is_returned = True
            task.is_completed = False
            if return_to_assignee is not None:
                assignee_ct, assignee_id = cls._actor_ref(return_to_assignee)
                if not assignee_ct or not assignee_id:
                    raise ValueError("return_to_assignee must be a concrete model instance.")
                task.current_assignee_content_type = assignee_ct
                task.current_assignee_object_id = assignee_id
            task.save()
            cls._sync_denormalized_status(task)
        return task

    @classmethod
    def reassign(cls, task, user, new_assignee, remark=""):
        if task.is_completed:
            raise PermissionDenied("This workflow has already been completed.")
        stage = task.current_stage
        if not stage.can_reassign:
            raise PermissionDenied("This stage cannot reassign.")

        assignee_ct, assignee_id = cls._actor_ref(new_assignee)
        if not assignee_ct or not assignee_id:
            raise ValueError("new_assignee must be a concrete model instance.")

        actor_ct, actor_id = cls._actor_ref(user)
        with transaction.atomic():
            ApprovalConfigurationTaskLog.objects.create(
                task=task,
                action="reassign",
                from_stage=stage,
                to_stage=stage,
                actor_content_type=actor_ct,
                actor_object_id=actor_id,
                remark=remark,
            )
            task.current_assignee_content_type = assignee_ct
            task.current_assignee_object_id = assignee_id
            task.save(update_fields=[
                "current_assignee_content_type",
                "current_assignee_object_id",
                "updated_at",
            ])
            if hasattr(task.target, "assignment_status"):
                task.target.assignment_status = "reassigned"
                task.target.save(update_fields=["assignment_status"])
        return task

    @classmethod
    def escalate(cls, task, user, remark=""):
        if task.is_completed:
            raise PermissionDenied("This workflow has already been completed.")
        stage = task.current_stage
        if not stage.can_escalate or not stage.escalation_role_id:
            raise PermissionDenied("This stage cannot escalate.")

        actor_ct, actor_id = cls._actor_ref(user)
        ApprovalConfigurationTaskLog.objects.create(
            task=task,
            action="escalate",
            from_stage=stage,
            to_stage=stage,
            actor_content_type=actor_ct,
            actor_object_id=actor_id,
            remark=remark,
        )
        return task

    @staticmethod
    def _sync_denormalized_status(task):
        target = task.target
        if target is None:
            return

        if task.is_completed:
            if hasattr(target, "status"):
                target.status = "approved"
            if hasattr(target, "assignment_status"):
                target.assignment_status = "approved"
        elif task.is_returned:
            if hasattr(target, "status"):
                target.status = "rejected"
            if hasattr(target, "assignment_status"):
                target.assignment_status = "rejected"
        else:
            if hasattr(target, "status"):
                target.status = "submitted"
            if hasattr(target, "assignment_status"):
                target.assignment_status = "in_progress"

        update_fields = []
        if hasattr(target, "status"):
            update_fields.append("status")
        if hasattr(target, "assignment_status"):
            update_fields.append("assignment_status")
        if hasattr(target, "reviewed_by"):
            target.reviewed_by = task.current_assignee if hasattr(task.current_assignee, "pk") else None
            update_fields.append("reviewed_by")
        if hasattr(target, "reviewed_at"):
            target.reviewed_at = timezone.now()
            update_fields.append("reviewed_at")
        if update_fields:
            target.save(update_fields=update_fields)


ApprovalConfigurationEngine = WorkflowConfigurationEngine
