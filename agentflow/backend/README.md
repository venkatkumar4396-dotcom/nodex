# AgentFlow Backend

Phase 1: Workflow JSON schema + Python executor running 3 agents in sequence from CLI.

## Setup

```bash
cd backend
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS/Linux  
source .venv/bin/activate

pip install -e ".[dev]"
```

## Run Demo Workflow (Phase 1)

```bash
# Set your LLM API key
$env:OPENAI_API_KEY="sk-..."   # or ANTHROPIC_API_KEY, GEMINI_API_KEY

# Run the demo: Trigger -> Research -> Classifier
python -m agentflow.scripts.run_demo

# Run tests
pytest
```

## Phase 1 Architecture

- `core/schemas/` — Pydantic models (source of truth for all data shapes)
- `core/executor/graph.py` — topological sort, execution layer builder
- `core/executor/runner.py` — WorkflowRunner orchestrates node execution
- `core/executor/node_runner.py` — single node: retry, timeout, validation
- `core/executor/context.py` — RunContext (shared run-level state)
- `core/agents/base.py` — BaseAgent abstract class + plugin registry
- `core/llm/client.py` — LiteLLM wrapper
- `core/llm/structured.py` — structured output with retry on schema error
- `scripts/run_demo.py` — CLI demo entry point
