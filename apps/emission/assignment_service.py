from django.db import transaction

from apps.organizations.models import ApprovalConfigurationTemplate
from apps.organizations.workflow_configuration_engine import WorkflowConfigurationEngine

from apps.common_events.event_context import EventContext
from apps.common_events.services import EventService

from apps.common_events.constants import (
    EMISSION,
    ASSIGNMENT,
    ASSIGNED,
)

from .models import (
    EmissionAssignment,
    EmissionAssignmentSource,
)

from .utils import generate_assignment_code


def create_emission_assignment(
    *,
    company_id,
    plant_id,
    financial_year_id,
    financial_month_id,
    scope_id,
    assignee,
    assigner,
    reviewer=None,
    due_date=None,
    priority="MEDIUM",
    notes="",
    source_ids=None,
    schedule=None,
):
    """
    Common service used by:

    1. Manual Assignment
    2. Automatic Scheduler
    """
    print("=" * 60)
    print("Creating Assignment")
    print("Company :", company_id)
    print("Plant   :", plant_id)
    print("FY      :", financial_year_id)
    print("Month   :", financial_month_id)
    print("Scope   :", scope_id)
    print("Sources :", source_ids)
    print("=" * 60)

    source_ids = source_ids or []

    assignment = EmissionAssignment.objects.create(

        assignment_code=generate_assignment_code(),

        company_id=company_id,

        plant_id=plant_id,

        financial_year_id=financial_year_id,

        financial_month_id=financial_month_id,

        scope_id=scope_id,

        schedule=schedule,

        assignee=assignee,

        assigner=assigner,

        reviewer=reviewer,

        due_date=due_date,

        priority=priority,

        notes=notes,

        status="ASSIGNED",

    )
    print("Assignment Created:", assignment.assignment_code)
    # ----------------------------------------
    # Create Assignment Sources
    # ----------------------------------------

    for source_id in source_ids:

        EmissionAssignmentSource.objects.create(

            assignment=assignment,

            source_id=source_id,

        )
    print("Sources Linked")

    # -------------------------------------------------------
    # Start Workflow
    # -------------------------------------------------------

    workflow_template = ApprovalConfigurationTemplate.objects.filter(
        company_id=assignment.company_id,
        is_active=True,
    ).first()

    if not workflow_template:
        raise ValueError(
            "No active EMISSION workflow configuration found for this company."
        )

    print("Workflow Template:", workflow_template)


    assignment.workflow_template = workflow_template
    assignment.save(update_fields=["workflow_template"])
    print("Workflow Started")
    workflow_task = WorkflowConfigurationEngine.start(
        template=workflow_template,
        target=assignment,
        first_assignee=assigner,
    )
    
    workflow_task = WorkflowConfigurationEngine.advance_to_next_stage(
        task=workflow_task,
        user=assigner,
        next_assignee=assignee,
    )
    print("Workflow Advanced")
    assignment.workflow_task = workflow_task
    assignment.save(update_fields=["workflow_task"])

    # -------------------------------------------------------
    # Publish Common Event
    # -------------------------------------------------------

    print("Publishing Event")

    context = EventContext(

        module=EMISSION,

        entity=ASSIGNMENT,

        action=ASSIGNED,

        target=assignment,

        actor=assigner,

    )

    EventService.publish(context)

    print("Event Published")
    print("Returning Assignment:", assignment.assignment_code)

    return assignment

    return assignment





