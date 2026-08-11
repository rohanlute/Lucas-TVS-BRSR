from apps.common_events.adapter_registry import ADAPTER_REGISTRY
from apps.notifications.services import TimesheetService


class TimesheetHandler:

    @classmethod
    def handle(cls, context):

        adapter = ADAPTER_REGISTRY.get(context.module)

        if not adapter:
            return

        timesheet = adapter.build_timesheet(context)

        if not timesheet:
            return

        # -------------------------------------------------------
        # Prevent duplicate for the same assignment and user
        # -------------------------------------------------------

        if TimesheetService.exists(
            assignment=timesheet["assignment"],
            user=timesheet["user"],
        ):
            return

        # -------------------------------------------------------
        # Create Timesheet
        # -------------------------------------------------------

        TimesheetService.create(**timesheet)