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
| **Phase 1** | ✅ Complete | Workflow JSON schema + Python executor + 5 agents + 25 tests |
| Phase 2 | 🔜 Next | Real tools (web search, HTTP, email) + structured output retries |
| Phase 3 | 🔜 | Branching, parallel, loops, Writer↔Reviewer feedback loop |
| Phase 4 | 🔜 | FastAPI + Postgres + Redis/Arq + WebSocket live events |
| Phase 5 | 🔜 | React Flow editor (drag/drop, configure, run, watch) |
| Phase 6 | 🔜 | Human Approval, Supervisor, RAG, Memory agents |
| Phase 7 | 🔜 | NL workflow generation, templates, cost dashboard |

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
