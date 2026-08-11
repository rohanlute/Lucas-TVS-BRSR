from .constants import *

from .adapters.emission_adapter import EmissionAdapter
from .adapters.brsr_adapter import BrsrAdapter
from .adapters.goals_adapter import GoalsAdapter


ADAPTER_REGISTRY = {

    EMISSION: EmissionAdapter,

    BRSR: BrsrAdapter,

    GOALS: GoalsAdapter,

}