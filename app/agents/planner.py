import os
import json
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from app.tools.budget import allocate_budget
from app.tools.distance import estimate_travel_time

PLANNER_TOOLS = [allocate_budget, estimate_travel_time]

SYSTEM_PROMPT = """You are an expert travel itinerary planner. Using the research data provided,
create a detailed day-by-day travel itinerary.

Your itinerary must include for each day:
1. A theme or focus for the day
2. Morning, afternoon, and evening activities with specific places
3. Meal recommendations (breakfast, lunch, dinner) with specific restaurants or food types
4. Accommodation suggestion
5. Estimated daily cost

Use the allocate_budget tool to properly distribute the budget across days and categories.
Use the estimate_travel_time tool to optimize the order of activities within each day.

Output your final itinerary as a valid JSON object with this structure:
{
  "destination": "string",
  "total_days": number,
  "total_budget": number,
  "currency": "string",
  "daily_plans": [
    {
      "day": number,
      "date": "YYYY-MM-DD",
      "theme": "string",
      "activities": [
        {"time": "HH:MM", "name": "string", "description": "string", "location": "string", "cost": number}
      ],
      "meals": [
        {"type": "breakfast|lunch|dinner", "venue": "string", "cuisine": "string", "cost": number}
      ],
      "accommodation": {"name": "string", "type": "string", "cost": number},
      "estimated_cost": number
    }
  ],
  "travel_tips": ["string"],
  "packing_suggestions": ["string"]
}

Return ONLY the JSON object, no extra text."""

REVISION_PROMPT = """The user has requested changes to the itinerary.

User feedback: {feedback}

Previous itinerary:
{previous_itinerary}

Research data:
{research_data}

Please revise the itinerary based on the user's feedback. Use tools as needed.
Return the updated itinerary as a valid JSON object with the same structure."""


def get_planner_agent():
    llm = ChatGroq(
        model="llama-3.3-70b-versatile",
        temperature=0.4,
        api_key=os.getenv("GROQ_API_KEY", ""),
    )
    return llm.bind_tools(PLANNER_TOOLS)


def _run_agent_loop(agent, messages: list, max_iterations: int = 6) -> str:
    tool_map = {t.name: t for t in PLANNER_TOOLS}

    for _ in range(max_iterations):
        response = agent.invoke(messages)
        messages.append(response)

        if not response.tool_calls:
            break

        for tc in response.tool_calls:
            tool_fn = tool_map.get(tc["name"])
            if tool_fn:
                result = tool_fn.invoke(tc["args"])
                messages.append(ToolMessage(content=str(result), tool_call_id=tc["id"]))

    return messages[-1].content if hasattr(messages[-1], "content") else ""


def _parse_itinerary(content: str) -> dict:
    content = content.strip()
    if content.startswith("```"):
        lines = content.split("\n")
        lines = lines[1:] if lines[0].startswith("```") else lines
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        content = "\n".join(lines)

    try:
        return json.loads(content)
    except json.JSONDecodeError:
        start = content.find("{")
        end = content.rfind("}") + 1
        if start != -1 and end > start:
            try:
                return json.loads(content[start:end])
            except json.JSONDecodeError:
                pass
        return {"raw_plan": content, "parse_error": True}


def run_planner(state: dict) -> dict:
    request = state["request"]
    research = state.get("research_data", "")
    agent = get_planner_agent()

    from datetime import date
    start = date.fromisoformat(request["start_date"])
    end = date.fromisoformat(request["end_date"])
    num_days = (end - start).days

    prompt = (
        f"Create a {num_days}-day itinerary for {request['destination']}.\n"
        f"Dates: {request['start_date']} to {request['end_date']}\n"
        f"Budget: {request['budget_min']}-{request['budget_max']} {request['currency']}\n"
        f"Travelers: {request.get('num_travelers', 1)}\n"
        f"Interests: {', '.join(request.get('interests', []))}\n\n"
        f"Research data:\n{research}\n\n"
        f"Use allocate_budget with total_budget={request['budget_max']}, "
        f"num_days={num_days}, num_travelers={request.get('num_travelers', 1)}, "
        f"currency='{request['currency']}' to plan the budget.\n"
        f"Use estimate_travel_time to optimize daily routes where you have location coordinates."
    )

    messages = [SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=prompt)]
    result = _run_agent_loop(agent, messages)
    itinerary = _parse_itinerary(result)

    return {"draft_itinerary": itinerary, "workflow_stage": "awaiting_review"}


def run_revision(state: dict) -> dict:
    request = state["request"]
    feedback = state.get("user_feedback") or ""
    previous = state.get("draft_itinerary", {})
    research = state.get("research_data", "")
    agent = get_planner_agent()

    prompt = REVISION_PROMPT.format(
        feedback=feedback,
        previous_itinerary=json.dumps(previous, indent=2),
        research_data=research,
    )

    messages = [SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=prompt)]
    result = _run_agent_loop(agent, messages)
    itinerary = _parse_itinerary(result)

    revision_count = state.get("revision_count", 0) + 1
    return {
        "draft_itinerary": itinerary,
        "workflow_stage": "awaiting_review",
        "revision_count": revision_count,
    }
