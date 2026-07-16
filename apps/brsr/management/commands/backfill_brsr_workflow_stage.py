from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand

from apps.brsr.models import Assignment
from apps.organizations.models import ApprovalConfigurationTask
from apps.organizations.workflow_configuration_engine import WorkflowConfigurationEngine


class Command(BaseCommand):
    help = "Advance BRSR assignment workflow tasks from question_assignment to data_entry."

    def handle(self, *args, **options):
        assignment_ct = ContentType.objects.get_for_model(Assignment)
        tasks = (
            ApprovalConfigurationTask.objects.select_related(
                "template",
                "current_stage",
                "current_assignee_content_type",
                "target_content_type",
            )
            .filter(
                target_content_type=assignment_ct,
                current_stage__stage_type="question_assignment",
            )
            .order_by("created_at")
        )

        updated = 0
        skipped = 0
        for task in tasks:
            next_stage = task.current_stage.next_stage()
            if not next_stage or next_stage.stage_type != "data_entry":
                skipped += 1
                continue

            assignment = task.target
            if assignment is None:
                skipped += 1
                continue

            current_assignee = getattr(assignment, "assignee", None)
            if current_assignee is None:
                skipped += 1
                continue

            WorkflowConfigurationEngine.advance_to_next_stage(
                task,
                getattr(assignment, "assigner", None) or current_assignee,
                remark="Backfilled to data entry stage.",
                next_assignee=current_assignee,
            )
            updated += 1

        self.stdout.write(self.style.SUCCESS(f"Updated {updated} task(s); skipped {skipped}."))
