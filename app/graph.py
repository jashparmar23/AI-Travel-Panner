from langgraph.graph import StateGraph, END
from app.state import TravelState
from app.agents.research import run_research
from app.agents.planner import run_planner, run_revision


def validate_request(state: TravelState) -> dict:
    request = state.get("request")
    if not request:
        return {"error": "No travel request provided", "workflow_stage": "failed"}
    required = ["destination", "start_date", "end_date", "budget_min", "budget_max"]
    missing = [f for f in required if f not in request]
    if missing:
        return {"error": f"Missing fields: {', '.join(missing)}", "workflow_stage": "failed"}
    return {"workflow_stage": "researching"}


def research_node(state: TravelState) -> dict:
    try:
        return run_research(state)
    except Exception as e:
        return {"error": f"Research failed: {str(e)}", "workflow_stage": "failed"}


def planner_node(state: TravelState) -> dict:
    try:
        return run_planner(state)
    except Exception as e:
        return {"error": f"Planning failed: {str(e)}", "workflow_stage": "failed"}


def revision_node(state: TravelState) -> dict:
    try:
        return run_revision(state)
    except Exception as e:
        return {"error": f"Revision failed: {str(e)}", "workflow_stage": "failed"}


def finalize_node(state: TravelState) -> dict:
    request = state.get("request", {})
    return {
        "final_plan": {
            "destination": request.get("destination", ""),
            "travel_dates": f"{request.get('start_date', '')} to {request.get('end_date', '')}",
            "num_travelers": request.get("num_travelers", 1),
            "itinerary": state.get("draft_itinerary", {}),
            "research_summary": state.get("research_data", ""),
        },
        "workflow_stage": "approved",
    }


def hitl_review_node(state: TravelState) -> dict:
    return {"workflow_stage": "awaiting_review"}


def _route_after_validation(state: TravelState) -> str:
    if state.get("workflow_stage") == "failed":
        return END
    return "research"


def _route_after_review(state: TravelState) -> str:
    action = state.get("review_action")
    if action == "approve":
        return "finalize"
    if action in ("reject", "modify"):
        return "revise"
    return END


def build_graph() -> StateGraph:
    graph = StateGraph(TravelState)

    graph.add_node("validate", validate_request)
    graph.add_node("research", research_node)
    graph.add_node("plan", planner_node)
    graph.add_node("hitl_review", hitl_review_node)
    graph.add_node("revise", revision_node)
    graph.add_node("finalize", finalize_node)

    graph.set_entry_point("validate")
    graph.add_conditional_edges("validate", _route_after_validation, {"research": "research", END: END})
    graph.add_edge("research", "plan")
    graph.add_edge("plan", "hitl_review")
    graph.add_edge("hitl_review", END)
    graph.add_conditional_edges("revise", lambda s: "hitl_review" if s.get("workflow_stage") != "failed" else END)
    graph.add_edge("finalize", END)

    return graph.compile()


def run_initial_workflow(state: TravelState) -> TravelState:
    """Run the graph from validate through to HITL pause."""
    graph = build_graph()
    result = graph.invoke(state)
    return result


def run_review_workflow(state: TravelState) -> TravelState:
    """Run post-review: either finalize or revise then pause again."""
    action = state.get("review_action")
    if action == "approve":
        return finalize_node(state)
    elif action in ("reject", "modify"):
        result = revision_node(state)
        return result
    return state
