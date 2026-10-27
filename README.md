# NodeX (AgentFlow)

> **Next-Generation Visual Agentic Workflow Platform**  
> An n8n-style workflow engine where every node is an autonomous AI agent that reasons, calls tools, and passes typed structured data to downstream nodes.

[![Tests](https://img.shields.io/badge/tests-132%2F132%20passing-brightgreen)](file:///agentflow/backend/tests)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](file:///agentflow/backend/pyproject.toml)
[![Frontend](https://img.shields.io/badge/frontend-React%2019%20%2B%20React%20Flow-blue)](file:///agentflow/frontend)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)

---

## 🌟 Overview

Traditional workflow engines (like Zapier or classic n8n) connect deterministic functions. **NodeX** elevates nodes to **autonomous AI agents** powered by modern LLMs (Moonshot/Kimi, OpenAI, Anthropic, Gemini, Ollama). Each agent can inspect context, reason, execute tools, validate structured output, and self-heal on schema errors.

### Core Capabilities

- **Topological Graph Execution**: High-throughput DAG engine using Kahn's algorithm with concurrent async node execution.
- **Provider-Agnostic LLM Routing**: Unified LiteLLM client supporting Moonshot AI (Kimi), OpenAI, Anthropic, Gemini, and local Ollama.
- **Structured Output & Self-Correction**: Enforces Pydantic output schemas with self-correcting validation loops.
- **Pluggable Agent Registry**: Clean separation between executor engine and agent implementations (`Research`, `Classifier`, `Writer`, `Reviewer`, `ManualTrigger`, `Email`, `HumanApproval`, `Supervisor`, `RAG`, `Memory`).
- **Production Tooling**: Built-in Web Search (Serper/DDG), HTTP request client, and Email dispatcher with encrypted credential store.
- **Advanced Control Flow**: Multi-path conditional branching, default fallback paths, self-healing Writer↔Reviewer feedback loops, and error handler edges.
- **Templating & Data Flow**: Mustache-style dynamic expression resolution (`{{research.output.summary}}`) connecting node inputs to upstream outputs.
- **Visual React Flow Studio**: Interactive node canvas with magnetic IN/OUT port handles, live running indicators, node inspection, and auto-DAG formatting.
- **Human-in-the-Loop Governance**: Real-time pause-on-approval gate with interactive sign-off banners and resume APIs.
- **AI Workflow Synthesis & Telemetry**: Natural language prompt-to-DAG generation and enterprise telemetry KPI dashboard.

---

## 🏗 Architecture & Roadmap

```
                    ┌────────────────────────┐
                    │     Manual Trigger     │
                    └───────────┬────────────┘
                                │ {lead_name, company, goal}
                    ┌───────────▼────────────┐
                    │     Research Agent     │
                    └───────────┬────────────┘
                                │ {summary, findings, confidence}
                    ┌───────────▼────────────┐
                    │    Classifier/Scorer   │
                    └───────────┬────────────┘
                                │ score >= 7 (Conditional branch)
                    ┌───────────▼────────────┐
                    │      Writer Agent      │◄──────────────────────────┐
                    └───────────┬────────────┘                           │
                                │ {subject, body, tone}                  │ not passed
                    ┌───────────▼────────────┐                           │ (Feedback Loop)
                    │     Reviewer Agent     ├───────────────────────────┘
                    └───────────┬────────────┘
                                │ passed == True (Forward edge)
                    ┌───────────▼────────────┐
                    │     Email Dispatch     │
                    └────────────────────────┘
```

| Phase | Description | Status |
|:---|:---|:---:|
| **Phase 1** | Workflow JSON Schema + Topological DAG Executor + Agent Registry + 5 Core Agents + Tests | **Complete** |
| **Phase 2** | Production Tools (Web Search, HTTP, Email) + Guardrails + Structured Retries + Credential Store | **Complete** |
| **Phase 3** | Advanced Control Flow (Branching, Loops, Parallel Fan-Out, Writer↔Reviewer Feedback Loop, Error Recovery) | **Complete** |
| **Phase 4** | Backend Services (FastAPI + SQLite Persistence + Real-Time SSE Stream + Run Telemetry) | **Complete** |
| **Phase 5** | Frontend Canvas (React 19 + Vite + React Flow + IN/OUT Handles + Live Run Visualizer) | **Complete** |
| **Phase 6** | Specialized Agents (Human-in-the-Loop Approval, Supervisor, RAG, Memory, Canvas Review Banner) | **Complete** |
| **Phase 7** | Natural Language Workflow Builder, Marketplace Templates & Enterprise Governance Analytics | **Complete (132/132 Tests Passing)** |

---

## 🚀 Quick Start

### 1. Prerequisites
- Python 3.10, 3.11, or 3.12
- Git

### 2. Installation

```bash
# Clone the repository
git clone https://github.com/venkatkumar4396-dotcom/nodex.git
cd nodex/agentflow/backend

# Create and activate virtual environment
python -m venv .venv
# On Windows:
.venv\Scripts\activate
# On Linux/macOS:
# source .venv/bin/activate

# Install dependencies in editable mode
pip install -e ".[dev]"
```

### 3. Environment Configuration

Copy the example environment template and configure your provider keys:

```bash
cp .env.example .env
```

Edit `.env` with your preferred model and API key:

```ini
# Kimi / Moonshot AI
MOONSHOT_API_KEY=your-api-key-here
DEFAULT_MODEL=moonshot/moonshot-v1-32k

# Or OpenAI / Anthropic / Gemini
OPENAI_API_KEY=
ANTHROPIC_API_KEY=
GEMINI_API_KEY=
```

> **Note:** `.env` is ignored by Git by design to keep your credentials safe.

### 4. Running the Demo Workflow

Execute the end-to-end B2B sales outreach agent pipeline:

```bash
python -m agentflow.scripts.run_demo
```

Custom lead execution:
```bash
python -m agentflow.scripts.run_demo --lead "Alex Rivera" --company "Stripe" --goal "Propose AI workflow partnership"
```

### 5. Running the Test Suite

Run the full pytest suite:

```bash
pytest tests/ -v
```

---

## 📁 Repository Structure

```
nodex/
├── .gitignore                    # Root Git ignore rules (protects credentials)
├── README.md                     # Project documentation & overview
└── agentflow/
    ├── README.md                 # AgentFlow subpackage guide
    └── backend/
        ├── .env.example          # Environment variable template
        ├── .gitignore            # Backend-specific ignore rules
        ├── pyproject.toml        # Dependencies and build metadata
        ├── src/
        │   └── agentflow/
        │       ├── config.py             # Typed Pydantic Settings
        │       ├── logging_config.py     # Structured logging
        │       ├── core/
        │       │   ├── agents/           # Agent implementations & Registry
        │       │   ├── executor/         # DAG graph runner, context, mapping
        │       │   ├── llm/              # Unified LiteLLM client & structured parser
        │       │   ├── schemas/          # Workflow, node, edge & tool schemas
        │       │   ├── tools/            # Base tool abstractions
        │       │   └── workflows/        # Pre-built workflow graphs
        │       └── scripts/
        │           └── run_demo.py       # Interactive CLI demo runner
        └── tests/                        # 51 unit & integration tests
```

---

## 🔒 Security & Best Practices

- **Zero Secret Commits**: Environment files (`.env*`) and private keys are strictly barred via multi-layered `.gitignore` patterns.
- **Deterministic Schema Contracts**: All nodes exchange typed Pydantic payloads to prevent hallucinations and malformed data cascades.
- **Fail-Safe Resource Limits**: Workflows enforce maximum step counts, execution timeouts, and cost caps per run.

---

## 📄 License

MIT License. See [LICENSE](LICENSE) for details.
