# AgentFlow Backend

Phase 2 ✅: Tools (web_search, http_request, email_send) + ToolRegistry + CredentialStore + Tool Loop + EmailAgent.

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

## Run Demo Workflow

```bash
# Kimi/Moonshot (default — set in .env)
python -m agentflow.scripts.run_demo

# Mock mode (offline, no API key needed)
python -m agentflow.scripts.run_demo --mock

# With custom lead
python -m agentflow.scripts.run_demo --lead "Jane Smith" --company "Acme Corp"

# Run tests
pytest -v
```

## Phase 2 — New Features

### Tool System
- `core/tools/base.py` — `BaseTool` interface (name, description, parameters_schema, execute)
- `core/tools/registry.py` — `ToolRegistry` singleton (plugin boundary, mirrors AgentRegistry)
- `core/tools/credentials.py` — `CredentialStore` with Fernet encryption
- `core/tools/tool_loop.py` — Multi-turn LLM ↔ tool-calling loop (native FC + prompt-based)

### Built-in Tools
| Tool | Name | Key | Notes |
|------|------|-----|-------|
| Web Search | `web_search` | `SERPER_API_KEY` or `BRAVE_SEARCH_API_KEY` | Stub fallback when no key |
| HTTP Request | `http_request` | `HTTP_BEARER_TOKEN` (optional) | 50KB response limit |
| Email Send | `email_send` | `SENDGRID_API_KEY` or SMTP vars | Stub mode by default |

### New Agents
- `EmailAgent` — action agent that composes and sends emails via `email_send` tool

### Architecture (Phases 1+2)
- `core/schemas/` — Pydantic models (single source of truth)
- `core/executor/graph.py` — topological sort, execution layer builder
- `core/executor/runner.py` — WorkflowRunner orchestrates node execution
- `core/executor/node_runner.py` — retry, timeout, validation, **tool resolution**
- `core/executor/context.py` — RunContext (shared run-level state)
- `core/agents/base.py` — BaseAgent abstract class
- `core/agents/registry.py` — AgentRegistry + `register_all_builtin_agents()`
- `core/tools/base.py` — BaseTool abstract class
- `core/tools/registry.py` — ToolRegistry + `register_all_builtin_tools()`
- `core/tools/credentials.py` — CredentialStore (Fernet encrypted)
- `core/tools/tool_loop.py` — Tool-calling loop (native + prompt-based)
- `core/llm/client.py` — LiteLLM wrapper
- `core/llm/structured.py` — structured output with retry on schema error
- `scripts/run_demo.py` — CLI demo entry point

## Test Count

| Phase | Tests |
|-------|-------|
| Phase 1 | 25 |
| Phase 2 | 81 (new) |
| **Total** | **106** |
