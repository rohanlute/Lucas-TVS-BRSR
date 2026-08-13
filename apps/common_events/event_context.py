from dataclasses import dataclass
from typing import Any


@dataclass
class EventContext:
    """
    Common Event Context

    Every event published in the platform
    is represented by this object.
    """

    module: str

    entity: str

    action: str

    target: Any

    actor: Any = None

    company: Any = None

    plant: Any = None

    request: Any = None

    metadata: dict | None = None