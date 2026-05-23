import os
import httpx
from langchain_core.tools import tool

SERPER_URL = "https://google.serper.dev/search"


@tool
def web_search(query: str) -> str:
    """Search the web for travel destination information using Google Search.
    Use this to find attractions, local tips, safety info, weather, and seasonal details.
    """
    api_key = os.getenv("SERPER_API_KEY", "")
    if not api_key:
        return "Error: SERPER_API_KEY not configured"

    headers = {"X-API-KEY": api_key, "Content-Type": "application/json"}
    payload = {"q": query, "num": 5}

    try:
        with httpx.Client(timeout=15) as client:
            resp = client.post(SERPER_URL, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPError as e:
        return f"Search request failed: {e}"

    results = []

    if "answerBox" in data:
        ab = data["answerBox"]
        results.append(f"Answer: {ab.get('answer') or ab.get('snippet', '')}")

    for item in data.get("organic", [])[:5]:
        title = item.get("title", "")
        snippet = item.get("snippet", "")
        results.append(f"- {title}: {snippet}")

    if "peopleAlsoAsk" in data:
        for paa in data["peopleAlsoAsk"][:3]:
            results.append(f"Q: {paa.get('question', '')} A: {paa.get('snippet', '')}")

    return "\n".join(results) if results else "No results found"
