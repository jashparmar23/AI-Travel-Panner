from pydantic import BaseModel, Field
from typing import Optional
from datetime import date
from enum import Enum


class TravelRequest(BaseModel):
    destination: str = Field(..., min_length=1, max_length=200)
    start_date: date
    end_date: date
    budget_min: float = Field(..., gt=0)
    budget_max: float = Field(..., gt=0)
    currency: str = Field(default="USD", max_length=3)
    interests: list[str] = Field(default_factory=list)
    num_travelers: int = Field(default=1, ge=1, le=20)

    def model_post_init(self, __context):
        if self.end_date <= self.start_date:
            raise ValueError("end_date must be after start_date")
        if self.budget_max < self.budget_min:
            raise ValueError("budget_max must be >= budget_min")


class ReviewAction(str, Enum):
    APPROVE = "approve"
    REJECT = "reject"
    MODIFY = "modify"


class ReviewRequest(BaseModel):
    action: ReviewAction
    feedback: Optional[str] = None


class DayPlan(BaseModel):
    day: int
    date: str
    theme: str
    activities: list[dict]
    meals: list[dict]
    accommodation: Optional[dict] = None
    estimated_cost: float


class DraftItinerary(BaseModel):
    destination: str
    total_days: int
    total_budget: float
    currency: str
    daily_plans: list[DayPlan]
    travel_tips: list[str]
    packing_suggestions: list[str]


class WorkflowStage(str, Enum):
    SUBMITTED = "submitted"
    RESEARCHING = "researching"
    PLANNING = "planning"
    AWAITING_REVIEW = "awaiting_review"
    REVISING = "revising"
    APPROVED = "approved"
    FAILED = "failed"


class PlanStatus(BaseModel):
    id: str
    stage: WorkflowStage
    draft_itinerary: Optional[dict] = None
    error: Optional[str] = None


class FinalPlan(BaseModel):
    id: str
    destination: str
    travel_dates: str
    num_travelers: int
    itinerary: dict
    research_summary: Optional[str] = None
