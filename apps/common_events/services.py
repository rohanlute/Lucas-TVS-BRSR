"""
Common Event Dispatcher
"""

from .registry import EVENT_REGISTRY
from .handler_registry import HANDLER_REGISTRY


class EventService:

    @classmethod
    def publish(cls, context):

        # ----------------------------------------
        # Identify Event
        # ----------------------------------------

        event = (
            context.module,
            context.entity,
            context.action,
        )

        # ----------------------------------------
        # Find Registered Handlers
        # ----------------------------------------

        handlers = EVENT_REGISTRY.get(
            event,
            [],
        )

        # ----------------------------------------
        # Execute Handlers
        # ----------------------------------------

        for handler_name in handlers:

            handler = HANDLER_REGISTRY.get(handler_name)

            if not handler:
                continue

            handler.handle(context)