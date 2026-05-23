from typing import TypedDict, Optional, Annotated
from operator import add


def replace_value(existing, new):
    return new


class TravelState(TypedDict, total=False):
    request: Annotated[dict, replace_value]
    research_data: Annotated[str, replace_value]
    draft_itinerary: Annotated[dict, replace_value]
    review_action: Annotated[Optional[str], replace_value]
    user_feedback: Annotated[Optional[str], replace_value]
    final_plan: Annotated[Optional[dict], replace_value]
    workflow_stage: Annotated[str, replace_value]
    error: Annotated[Optional[str], replace_value]
    revision_count: Annotated[int, replace_value]


class PlanStore:
    """Thread-safe in-memory store for plan states keyed by plan ID."""

    def __init__(self):
        self._store: dict[str, TravelState] = {}

    def get(self, plan_id: str) -> Optional[TravelState]:
        return self._store.get(plan_id)

    def set(self, plan_id: str, state: TravelState):
        self._store[plan_id] = state

    def update(self, plan_id: str, updates: dict):
        if plan_id in self._store:
            self._store[plan_id].update(updates)

    def exists(self, plan_id: str) -> bool:
        return plan_id in self._store


plan_store = PlanStore()
