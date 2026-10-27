# AgentFlow

An n8n-style visual workflow platform where every node is an AI agent.
Agents reason, call tools, and pass structured output to the next agent.

## Quick Start (Phase 1 — CLI only)

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # macOS/Linux

pip install -e ".[dev]"
copy .env.example .env        # then add your API key
```

Set your LLM API key in `.env`:
```
OPENAI_API_KEY=sk-...
DEFAULT_MODEL=gpt-4o-mini
```

Run the demo workflow (Trigger → Research → Classifier → Writer → Reviewer):
```bash
python -m agentflow.scripts.run_demo

# Custom lead
python -m agentflow.scripts.run_demo --lead "Sarah Chen" --company "TechCorp" --model "gpt-4o"

# Using Anthropic Claude
python -m agentflow.scripts.run_demo --model "claude-3-5-sonnet-20241022"

# Using local Ollama
python -m agentflow.scripts.run_demo --model "ollama/llama3"
```

Run tests:
```bash
pytest -v
```

## Build Phases

| Phase | Status | What it includes |
|-------|--------|-----------------|
| **Phase 1** | ✅ Complete | Workflow JSON schema + Python DAG executor + 5 core agents |
| **Phase 2** | ✅ Complete | Real tools (Web Search, HTTP, Email), Credential Store, Structured output self-correction |
| **Phase 3** | ✅ Complete | Advanced control flow: Multi-path branching, Default edges, Loops, Writer↔Reviewer feedback loop, Error routing |
| **Phase 4** | ✅ Complete | Backend Services: FastAPI + SQLite persistence + Server-Sent Events (SSE) live streaming |
| **Phase 5** | ✅ Complete | Frontend Studio: React Flow visual canvas, magnetic IN/OUT ports, Node/Edge Inspectors, live run pulses |
| **Phase 6** | ✅ Complete | Specialized Agents: Human Approval Gate with pause/resume, Supervisor, RAG with citations, Memory |
| **Phase 7** | ✅ Complete | Natural language AI workflow generator, Telemetry & Analytics dashboard, Run cancellation |

## Running the Web Application

### Option A: Run everything with one click (Windows)
Double-click `run-all.bat` or run:
```bat
.\run-all.bat
```

### Option B: Run individually
1. **Backend**:
   ```powershell
   cd backend
   .venv\Scripts\python -m uvicorn agentflow.api.app:app --host 127.0.0.1 --port 8000
   ```
2. **Frontend**:
   ```powershell
   cd frontend
   npm run dev
   ```
- **Web Canvas UI**: http://localhost:5173
- **Interactive Swagger API Docs**: http://127.0.0.1:8000/docs
- **Automated Test Suite (132 tests)**: `pytest` in `backend`

## Architecture

See the [Architecture Document](../agentflow_architecture.md) for full details.

### Key Design Decisions

- **Pydantic schemas** are the single source of truth for all data shapes
- **AgentRegistry** is the plugin boundary — add agents without changing the engine
- **Topological execution** (Kahn's algorithm) enables parallel fan-out naturally
- **LiteLLM** provides one interface for OpenAI, Claude, Gemini, Ollama
- **RunContext** tracks shared state, costs, and step counts for each run
- **Structured output + retry** — validation errors are fed back to the LLM for self-correction

### Demo Workflow

```
[Manual Trigger]
      ↓  {lead_name, company, goal}
[Research Agent]         # LLM-powered company/lead research
      ↓  {summary, key_findings, confidence}
[Classifier/Scorer]      # Scores lead 1-10
      ├─ score < 7  →  STOP
      └─ score ≥ 7  ↓
[Writer Agent]           # Writes personalized outreach email
      ↓  {subject, body, tone}
[Reviewer Agent]         # Scores email quality 1-10 (Phase 3: feedback loop)
```
