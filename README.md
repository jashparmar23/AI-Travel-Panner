# AI Travel Planner

A multi-agent travel planning system built with **LangGraph**, **FastAPI**, and **Groq LLM**. The system uses two specialized AI agents orchestrated through a StateGraph workflow with human-in-the-loop (HITL) approval.

## Architecture

```
User Request
     |
     v
[Orchestrator - LangGraph StateGraph]
     |
     v
[Validate Request]
     |
     v
[Research Agent] -----> Tools: Web Search (Serper), Currency Converter
     |
     v
[Itinerary Planner Agent] -----> Tools: Budget Allocator, Distance/Time Calculator
     |
     v
[HITL Review] <--- User: approve / reject / modify
     |                    |
     v                    v
[Finalize]          [Revise] --> back to HITL Review
     |
     v
[Final Plan Output]
```

### Components

**Orchestrator (`app/graph.py`)**
- LangGraph `StateGraph` managing the workflow
- Nodes: validate, research, plan, hitl_review, revise, finalize
- Conditional routing based on workflow stage and user feedback
- State persistence across HITL pause/resume cycles

**Research Agent (`app/agents/research.py`)**
- Groq LLM (llama-3.3-70b-versatile) with tool calling
- Tool 1: **Web Search** - Serper API for real-time destination research
- Tool 2: **Currency Converter** - Open ExchangeRate API for budget conversion

**Itinerary Planner Agent (`app/agents/planner.py`)**
- Groq LLM with tool calling
- Tool 1: **Budget Allocator** - Distributes budget across days and categories (accommodation 35%, food 25%, activities 25%, transport 15%)
- Tool 2: **Distance/Time Calculator** - Haversine distance with nearest-neighbor route optimization

## Setup

### Prerequisites
- Python 3.11+
- Groq API key ([console.groq.com](https://console.groq.com))
- Serper API key ([serper.dev](https://serper.dev))

### Installation

```bash
git clone https://github.com/jashparmar23/AI-Travel-Panner.git
cd AI-Travel-Panner
python -m venv .venv
.venv\Scripts\activate   # Windows
# source .venv/bin/activate  # Linux/Mac
pip install -r requirements.txt
```

### Environment Variables

```bash
cp .env.example .env
# Edit .env with your API keys:
# GROQ_API_KEY=your_key
# SERPER_API_KEY=your_key
```

### Run

```bash
uvicorn app.main:app --reload
```

API docs available at `http://localhost:8000/docs`

## API Endpoints

| Method | Endpoint | Purpose | Status Codes |
|--------|----------|---------|-------------|
| POST | `/plan` | Submit a new travel request | 201, 422 |
| GET | `/plan/{id}` | Get plan status and draft | 200, 404 |
| POST | `/plan/{id}/review` | Submit HITL feedback | 200, 404, 409 |
| GET | `/plan/{id}/final` | Get finalized plan | 200, 404, 409 |
| GET | `/health` | Health check | 200 |

## Example API Requests

### 1. Create a Plan

```bash
curl -X POST http://localhost:8000/plan \
  -H "Content-Type: application/json" \
  -d '{
    "destination": "Tokyo, Japan",
    "start_date": "2025-07-01",
    "end_date": "2025-07-05",
    "budget_min": 1500,
    "budget_max": 3000,
    "currency": "USD",
    "interests": ["temples", "street food", "anime", "technology"],
    "num_travelers": 2
  }'
```

Response:
```json
{
  "id": "a1b2c3d4-...",
  "status": "submitted",
  "message": "Travel plan workflow started"
}
```

### 2. Check Status

```bash
curl http://localhost:8000/plan/{plan_id}
```

Response (when ready for review):
```json
{
  "id": "a1b2c3d4-...",
  "stage": "awaiting_review",
  "draft_itinerary": { ... },
  "error": null
}
```

### 3. Review Plan

Approve:
```bash
curl -X POST http://localhost:8000/plan/{plan_id}/review \
  -H "Content-Type: application/json" \
  -d '{"action": "approve"}'
```

Reject with feedback:
```bash
curl -X POST http://localhost:8000/plan/{plan_id}/review \
  -H "Content-Type: application/json" \
  -d '{
    "action": "reject",
    "feedback": "Add more food-focused activities and replace the museum on day 3 with a cooking class"
  }'
```

Modify:
```bash
curl -X POST http://localhost:8000/plan/{plan_id}/review \
  -H "Content-Type: application/json" \
  -d '{
    "action": "modify",
    "feedback": "Change day 2 hotel to something closer to Shibuya"
  }'
```

### 4. Get Final Plan

```bash
curl http://localhost:8000/plan/{plan_id}/final
```

## Docker

### Build and Run

```bash
docker build -t ai-travel-planner .
docker run -p 8000:8000 \
  -e GROQ_API_KEY=your_key \
  -e SERPER_API_KEY=your_key \
  ai-travel-planner
```

### Deploy on Render

1. Push to GitHub
2. Create a new Web Service on Render
3. Select Docker environment
4. Add environment variables: `GROQ_API_KEY`, `SERPER_API_KEY`
5. Deploy

## Design Decisions and Tradeoffs

### State Management
- **Decision**: In-memory dictionary store for plan states
- **Tradeoff**: Simple and fast, but data is lost on restart. Production would use Redis or PostgreSQL for persistence and horizontal scaling.

### LLM Choice
- **Decision**: Groq with llama-3.3-70b-versatile
- **Rationale**: Free tier, fast inference (~200 tokens/s), strong tool-calling support. Tradeoff vs OpenAI/Anthropic: slightly lower quality but zero cost.

### HITL Implementation
- **Decision**: Graph execution runs to completion and stops at the review node by design. State is persisted in the store. Review endpoint triggers the post-review workflow (finalize or revise).
- **Tradeoff**: Simpler than true interrupt-based HITL but achieves the same user experience. The workflow is effectively split into pre-review and post-review phases.

### Tool Design
- **Budget Allocator**: Algorithmic (no external API), uses fixed category weights. Could be improved with ML-based pricing models.
- **Distance Calculator**: Uses Haversine formula with nearest-neighbor heuristic (O(n^2) greedy). Optimal for small N (daily activities). For large N, would use 2-opt or OR-Tools.
- **Currency Converter**: Uses free ExchangeRate API (no signup required). Rate-limited but sufficient for this use case.

### Background Processing
- **Decision**: FastAPI `BackgroundTasks` for running the LangGraph workflow
- **Tradeoff**: Works for single-instance deployment. Production would use Celery/Redis for distributed task processing.

## Future Improvements

- **Persistent storage**: PostgreSQL/Redis for state persistence across restarts
- **Streaming responses**: SSE or WebSocket for real-time progress updates during research/planning
- **Caching**: Cache research results for popular destinations to reduce API calls
- **Rate limiting**: Per-user rate limits on plan creation
- **Authentication**: JWT-based auth for multi-user support
- **Testing**: Integration tests with mocked LLM responses
- **Monitoring**: Structured logging, OpenTelemetry tracing for agent execution
- **Multi-destination**: Support for multi-city trip planning with inter-city transit optimization

## Assumptions

1. Single-instance deployment (no horizontal scaling needed for demo)
2. Plans are short-lived and in-memory storage is acceptable
3. Groq free tier is sufficient for evaluation (rate limits may apply under load)
4. Serper free tier provides enough queries for testing
5. Currency exchange rates from the free API are sufficiently accurate for budget estimation
