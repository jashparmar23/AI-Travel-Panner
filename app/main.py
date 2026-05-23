import uuid
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import HTMLResponse


from app.models import (
    TravelRequest,
    ReviewRequest,
    ReviewAction,
    PlanStatus,
    FinalPlan,
    WorkflowStage,
)
from app.state import plan_store
from app.graph import run_initial_workflow, run_review_workflow


load_dotenv()


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(
    title="AI Travel Planner",
    description="Multi-agent travel planning system with human-in-the-loop approval",
    version="1.0.0",
    lifespan=lifespan,
)


@app.get("/", response_class=HTMLResponse)
async def serve_index():
    import os
    file_path = os.path.join(os.path.dirname(__file__), "templates", "index.html")
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Frontend file not found")
    with open(file_path, "r", encoding="utf-8") as f:
        return f.read()



def _run_workflow_sync(plan_id: str):
    state = plan_store.get(plan_id)
    if not state:
        return
    try:
        result = run_initial_workflow(state)
        plan_store.set(plan_id, result)
    except Exception as e:
        plan_store.update(plan_id, {"error": str(e), "workflow_stage": "failed"})


def _run_review_sync(plan_id: str):
    state = plan_store.get(plan_id)
    if not state:
        return
    try:
        result = run_review_workflow(state)
        current = plan_store.get(plan_id)
        current.update(result)
        plan_store.set(plan_id, current)
    except Exception as e:
        plan_store.update(plan_id, {"error": str(e), "workflow_stage": "failed"})


@app.post("/plan", status_code=201)
async def create_plan(request: TravelRequest, background_tasks: BackgroundTasks):
    plan_id = str(uuid.uuid4())

    initial_state = {
        "request": request.model_dump(mode="json"),
        "research_data": "",
        "draft_itinerary": {},
        "review_action": None,
        "user_feedback": None,
        "final_plan": None,
        "workflow_stage": "submitted",
        "error": None,
        "revision_count": 0,
    }
    plan_store.set(plan_id, initial_state)

    background_tasks.add_task(_run_workflow_sync, plan_id)

    return {"id": plan_id, "status": "submitted", "message": "Travel plan workflow started"}


@app.get("/plan/{plan_id}")
async def get_plan_status(plan_id: str):
    state = plan_store.get(plan_id)
    if not state:
        raise HTTPException(status_code=404, detail="Plan not found")

    response = PlanStatus(
        id=plan_id,
        stage=state.get("workflow_stage", "submitted"),
        draft_itinerary=state.get("draft_itinerary") if state.get("draft_itinerary") else None,
        error=state.get("error"),
    )
    return response


@app.post("/plan/{plan_id}/review")
async def review_plan(plan_id: str, review: ReviewRequest, background_tasks: BackgroundTasks):
    state = plan_store.get(plan_id)
    if not state:
        raise HTTPException(status_code=404, detail="Plan not found")

    current_stage = state.get("workflow_stage")
    if current_stage != "awaiting_review":
        raise HTTPException(
            status_code=409,
            detail=f"Plan is in '{current_stage}' stage, not ready for review",
        )

    plan_store.update(plan_id, {
        "review_action": review.action.value,
        "user_feedback": review.feedback,
        "workflow_stage": "revising" if review.action != ReviewAction.APPROVE else "approved",
    })

    if review.action == ReviewAction.APPROVE:
        state = plan_store.get(plan_id)
        result = run_review_workflow(state)
        current = plan_store.get(plan_id)
        current.update(result)
        plan_store.set(plan_id, current)
        return {"status": "approved", "message": "Plan finalized"}

    background_tasks.add_task(_run_review_sync, plan_id)
    return {"status": "revising", "message": "Plan sent for revision based on feedback"}


@app.get("/plan/{plan_id}/final")
async def get_final_plan(plan_id: str):
    state = plan_store.get(plan_id)
    if not state:
        raise HTTPException(status_code=404, detail="Plan not found")

    if state.get("workflow_stage") != "approved":
        raise HTTPException(
            status_code=409,
            detail=f"Plan not yet approved. Current stage: {state.get('workflow_stage')}",
        )

    final = state.get("final_plan")
    if not final:
        raise HTTPException(status_code=500, detail="Final plan data missing")

    return FinalPlan(
        id=plan_id,
        destination=final.get("destination", ""),
        travel_dates=final.get("travel_dates", ""),
        num_travelers=final.get("num_travelers", 1),
        itinerary=final.get("itinerary", {}),
        research_summary=final.get("research_summary"),
    )


@app.get("/health")
async def health_check():
    return {"status": "healthy"}
