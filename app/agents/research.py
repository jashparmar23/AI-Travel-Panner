import os
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from app.tools.web_search import web_search
from app.tools.currency import convert_currency

RESEARCH_TOOLS = [web_search, convert_currency]

SYSTEM_PROMPT = """You are a travel research specialist. Given a destination and travel parameters,
gather comprehensive information by using the available tools.

Your research should cover:
1. Top attractions and must-visit places
2. Local tips and cultural considerations
3. Safety information and advisories
4. Weather and seasonal factors for the travel dates
5. Local currency and cost of living estimates
6. Transportation options within the destination

Use the web_search tool to find current information about the destination.
Use the convert_currency tool to provide budget estimates in local currency.

Compile your findings into a structured research report. Be factual and concise."""


def get_research_agent():
    llm = ChatGroq(
        model="llama-3.3-70b-versatile",
        temperature=0.3,
        api_key=os.getenv("GROQ_API_KEY", ""),
    )
    return llm.bind_tools(RESEARCH_TOOLS)


def _run_agent_loop(agent, messages: list, max_iterations: int = 6) -> str:
    tool_map = {t.name: t for t in RESEARCH_TOOLS}

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


def run_research(state: dict) -> dict:
    request = state["request"]
    agent = get_research_agent()

    prompt = (
        f"Research the destination: {request['destination']}\n"
        f"Travel dates: {request['start_date']} to {request['end_date']}\n"
        f"Budget: {request['budget_min']}-{request['budget_max']} {request['currency']}\n"
        f"Interests: {', '.join(request.get('interests', []))}\n"
        f"Number of travelers: {request.get('num_travelers', 1)}\n\n"
        f"Use the web_search tool to research this destination thoroughly. "
        f"Use convert_currency to show budget in local currency if different from {request['currency']}."
    )

    messages = [SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=prompt)]
    result = _run_agent_loop(agent, messages)
    return {"research_data": result, "workflow_stage": "planning"}
