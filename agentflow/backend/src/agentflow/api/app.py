"""
FastAPI application — the HTTP entry point for AgentFlow.

Architecture:
  - Mounts all API routes from the routes_* modules
  - Configures CORS for the React frontend (localhost:5173)
  - Provides a health-check endpoint
  - On startup: creates all database tables (dev mode)
  - Serves the React frontend static files in production mode
"""
from __future__ import annotations

from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from agentflow.api.routes_runs import router as runs_router
from agentflow.api.routes_workflows import router as workflows_router
from agentflow.api.schemas import HealthResponse
from agentflow.config import settings
from agentflow.db.engine import Base, engine
from agentflow.marketplace.routes_marketplace import router as marketplace_router
from agentflow.meta.routes_meta import router as meta_router

log = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown lifecycle."""
    # ── Startup ──────────────────────────────────────────────────────────
    log.info("database_init", msg="Creating database tables if they don't exist...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    log.info("database_ready")

    # Register builtin agents and tools
    from agentflow.core.agents.registry import (
        register_all_builtin_agents,
        register_all_builtin_tools,
    )
    register_all_builtin_agents()
    register_all_builtin_tools()

    yield

    # ── Shutdown ─────────────────────────────────────────────────────────
    log.info("shutdown", msg="Disposing database engine...")
    await engine.dispose()


app = FastAPI(
    title="AgentFlow",
    description="Visual AI Agent Workflow Platform — API",
    version="0.1.0",
    lifespan=lifespan,
)

# ── CORS ──────────────────────────────────────────────────────────────────
# Allow the React dev server (Vite on port 5173) and common dev origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── API Routes ────────────────────────────────────────────────────────────
app.include_router(workflows_router)
app.include_router(runs_router)
app.include_router(meta_router)
app.include_router(marketplace_router)


@app.get("/api/health", response_model=HealthResponse, tags=["system"])
async def health_check() -> HealthResponse:
    """Simple health check endpoint."""
    return HealthResponse(status="ok", version="0.1.0", database="postgresql")


CORE_AGENT_PRIMITIVES = [
    # ── 1. Triggers
    {
        "type": "trigger_manual",
        "label": "Manual Trigger",
        "category": "Triggers",
        "color": "#6366f1",
        "icon": "⚡",
        "description": "Initiate workflow DAG execution with custom test input payloads or parameters.",
    },
    {
        "type": "trigger_webhook",
        "label": "Webhook Trigger",
        "category": "Triggers",
        "color": "#3b82f6",
        "icon": "🌐",
        "description": "Real-time incoming HTTP POST webhook listener that triggers workflows automatically.",
    },
    {
        "type": "trigger_cron",
        "label": "Schedule / Cron Trigger",
        "category": "Triggers",
        "color": "#8b5cf6",
        "icon": "⏰",
        "description": "Automated recurring cron scheduler for hourly, daily, or periodic agent execution.",
    },

    # ── 2. Core Reasoning & Intelligence
    {
        "type": "prompt",
        "label": "Prompt / LLM Node",
        "category": "Core Reasoning",
        "color": "#a855f7",
        "icon": "🧠",
        "description": "Direct multi-model LLM reasoning with customized persona, system directives, and structured output.",
    },
    {
        "type": "research",
        "label": "Deep Research Agent",
        "category": "Core Reasoning",
        "color": "#0ea5e9",
        "icon": "🔍",
        "description": "Autonomous multi-source investigator that queries web sources, extracts facts, and compiles cited findings.",
    },
    {
        "type": "writer",
        "label": "Copywriter & Content Agent",
        "category": "Core Reasoning",
        "color": "#ec4899",
        "icon": "✍️",
        "description": "Generates high-conversion emails, blog drafts, documentation, and executive messaging.",
    },
    {
        "type": "summarizer",
        "label": "Executive Summarizer",
        "category": "Core Reasoning",
        "color": "#14b8a6",
        "icon": "📝",
        "description": "Distills long articles, transcripts, research dumps, and documents into crisp executive takeaways.",
    },
    {
        "type": "translator",
        "label": "Multi-Lingual Translator",
        "category": "Core Reasoning",
        "color": "#6366f1",
        "icon": "🌍",
        "description": "Context-preserving multi-lingual translation and localization across 50+ languages.",
    },

    # ── 3. Autonomous Actions & Integrations
    {
        "type": "tool",
        "label": "Autonomous Tool Loop",
        "category": "Autonomous Actions",
        "color": "#0284c7",
        "icon": "🛠️",
        "description": "Multi-turn ReAct tool execution loop with search, API fetching, and structured observation feedback.",
    },
    {
        "type": "scraper",
        "label": "Web Scraper & Reader",
        "category": "Autonomous Actions",
        "color": "#f97316",
        "icon": "🕷️",
        "description": "Extracts clean Markdown, structured article text, metadata, and HTML tables from live URLs.",
    },
    {
        "type": "http_api",
        "label": "REST / HTTP API Node",
        "category": "Autonomous Actions",
        "color": "#2563eb",
        "icon": "🌐",
        "description": "Executes authenticated HTTP requests (GET/POST/PUT/DELETE) with JSON payloads and custom headers.",
    },
    {
        "type": "email",
        "label": "Email Dispatcher",
        "category": "Autonomous Actions",
        "color": "#059669",
        "icon": "✉️",
        "description": "Dispatches formatted transactional emails with recipient variables, CC/BCC, and HTML templates.",
    },
    {
        "type": "messaging",
        "label": "Slack & Teams Messaging",
        "category": "Autonomous Actions",
        "color": "#4f46e5",
        "icon": "💬",
        "description": "Dispatches rich interactive notifications, alerts, and formatted message cards to chat channels.",
    },
    {
        "type": "github_ops",
        "label": "GitHub Ops Agent",
        "category": "Autonomous Actions",
        "color": "#24292f",
        "icon": "🐙",
        "description": "Automates issue triage, PR review summaries, commit analysis, and repository workflows.",
    },
    {
        "type": "browser_operator",
        "label": "Browser Operator",
        "category": "Autonomous Actions",
        "color": "#f97316",
        "icon": "🌐",
        "description": "Autonomous browser agent that operates websites without APIs using step-by-step actions, domain allowlists, and injection defense.",
    },

    # ── 4. Decision, Logic & Flow
    {
        "type": "router",
        "label": "Classifier / Router",
        "category": "Decision & Flow",
        "color": "#d946ef",
        "icon": "🔀",
        "description": "Evaluates inputs against configurable criteria and routes execution down targeted conditional paths.",
    },
    {
        "type": "validator",
        "label": "Schema & Quality Validator",
        "category": "Decision & Flow",
        "color": "#059669",
        "icon": "🛡️",
        "description": "Validates upstream payloads against strict JSON schemas, ensuring data integrity before downstream execution.",
    },
    {
        "type": "error_handler",
        "label": "Error Boundary / Fallback",
        "category": "Decision & Flow",
        "color": "#dc2626",
        "icon": "🚨",
        "description": "Catches node execution failures, triggers fallback rescue logic, and sends incident alerts.",
    },

    # ── 5. Human Oversight & Safety
    {
        "type": "human_approval",
        "label": "Human Gate (HITL)",
        "category": "Human Oversight",
        "color": "#f59e0b",
        "icon": "⏸️",
        "description": "Pauses workflow for human sign-off, reviewer notes, and payload validation before resuming.",
    },
    {
        "type": "guardrail",
        "label": "AI Guardrail & Safety Gate",
        "category": "Human Oversight",
        "color": "#e11d48",
        "icon": "🧱",
        "description": "Scans inputs and outputs for PII leaks, prompt injection attacks, toxic content, and hallucinations.",
    },

    # ── 6. Computation & Data Intelligence
    {
        "type": "code",
        "label": "Code Sandbox",
        "category": "Computation & Code",
        "color": "#10b981",
        "icon": "💻",
        "description": "Executes deterministic Python transformations, mathematical calculations, and structured data reshaping.",
    },
    {
        "type": "sql",
        "label": "Database & SQL Agent",
        "category": "Computation & Code",
        "color": "#0284c7",
        "icon": "🗄️",
        "description": "Generates and executes SQL queries, introspects database schemas, and summarizes relational datasets.",
    },
    {
        "type": "data_analyst",
        "label": "Data Analyst Agent",
        "category": "Computation & Code",
        "color": "#6366f1",
        "icon": "📈",
        "description": "Calculates statistical metrics, uncovers trends, detects anomalies, and generates chart payloads.",
    },
    {
        "type": "document_parser",
        "label": "Document & PDF Parser",
        "category": "Computation & Code",
        "color": "#8b5cf6",
        "icon": "📄",
        "description": "Extracts text, financial tables, and key-value fields from PDFs, scanned documents, and spreadsheets.",
    },
    {
        "type": "vision",
        "label": "Multimodal Vision Agent",
        "category": "Computation & Code",
        "color": "#f43f5e",
        "icon": "👁️",
        "description": "Analyzes screenshots, UI designs, infographics, diagrams, and visual receipts with multimodal reasoning.",
    },

    # ── 7. Knowledge, Memory & Protocols
    {
        "type": "rag",
        "label": "RAG Knowledge Agent",
        "category": "Protocols & MCP",
        "color": "#06b6d4",
        "icon": "📚",
        "description": "Performs retrieval-augmented semantic search over embedded documentation and vector collections.",
    },
    {
        "type": "memory",
        "label": "Persistent Memory Bank",
        "category": "Protocols & MCP",
        "color": "#d946ef",
        "icon": "🧠",
        "description": "Cross-session memory store that reads, writes, and recalls persistent facts and user context.",
    },
    {
        "type": "mcp_client",
        "label": "MCP Client Node",
        "category": "Protocols & MCP",
        "color": "#0891b2",
        "icon": "🔌",
        "description": "Model Context Protocol client connecting local file systems, SQLite databases, and remote MCP servers.",
    },

    # ── 8. Synthesis & Swarm Orchestration
    {
        "type": "synthesizer",
        "label": "Synthesizer Agent",
        "category": "Synthesis & Output",
        "color": "#14b8a6",
        "icon": "📊",
        "description": "Aggregates multi-branch parallel outputs, resolves discrepancies, and formats executive deliverables.",
    },
    {
        "type": "supervisor",
        "label": "Supervisor & Swarm Team",
        "category": "Synthesis & Output",
        "color": "#7c3aed",
        "icon": "👔",
        "description": "Multi-agent team supervisor that deconstructs complex goals, delegates tasks, and synthesizes results.",
    },
]


@app.get("/api/agent-types", tags=["system"])
async def list_agent_types() -> list[dict]:
    """Return the curated core agent primitives for the node palette."""
    return CORE_AGENT_PRIMITIVES


@app.get("/api/tools", tags=["system"])
async def list_tools() -> list[dict]:
    """Return all available built-in and plugin tools."""
    from agentflow.core.tools.registry import register_all_builtin_tools, tool_registry
    register_all_builtin_tools()

    result = []
    for name in tool_registry.list_registered():
        tool = tool_registry.get(name)
        result.append({
            "name": tool.name,
            "description": getattr(tool, "description", ""),
            "parameters_schema": getattr(tool, "parameters_schema", {}),
        })
    return result


def _mask_key(key: str | None) -> str:
    if not key or len(key) < 8:
        return ""
    return f"{key[:5]}...{key[-4:]}"


class KeysUpdateRequest(BaseModel):
    openrouter_api_key: str | None = None
    openrouter_api_key_backup: str | None = None
    openrouter_api_key_tertiary: str | None = None
    moonshot_api_key: str | None = None
    openai_api_key: str | None = None
    anthropic_api_key: str | None = None
    gemini_api_key: str | None = None
    default_model: str | None = None
    mock_llm: bool | None = None


@app.get("/api/settings/keys", tags=["settings"])
async def get_settings_keys() -> dict:
    """Return configured status and masked previews for LLM provider API keys."""
    return {
        "openrouter_api_key_configured": bool(settings.openrouter_api_key),
        "openrouter_api_key_preview": _mask_key(settings.openrouter_api_key),
        "openrouter_api_key_backup_configured": bool(settings.openrouter_api_key_backup),
        "openrouter_api_key_backup_preview": _mask_key(settings.openrouter_api_key_backup),
        "openrouter_api_key_tertiary_configured": bool(settings.openrouter_api_key_tertiary),
        "openrouter_api_key_tertiary_preview": _mask_key(settings.openrouter_api_key_tertiary),
        "moonshot_api_key_configured": bool(settings.moonshot_api_key),
        "moonshot_api_key_preview": _mask_key(settings.moonshot_api_key),
        "openai_api_key_configured": bool(settings.openai_api_key),
        "openai_api_key_preview": _mask_key(settings.openai_api_key),
        "anthropic_api_key_configured": bool(settings.anthropic_api_key),
        "anthropic_api_key_preview": _mask_key(settings.anthropic_api_key),
        "gemini_api_key_configured": bool(settings.gemini_api_key),
        "gemini_api_key_preview": _mask_key(settings.gemini_api_key),
        "default_model": settings.default_model,
        "mock_llm": settings.mock_llm,
    }


@app.post("/api/settings/keys", tags=["settings"])
async def update_settings_keys(req: KeysUpdateRequest) -> dict:
    """Save API keys into runtime environment and persist to backend/.env."""
    import os
    from pathlib import Path

    updates = {}
    if req.openrouter_api_key is not None:
        settings.openrouter_api_key = req.openrouter_api_key.strip()
        os.environ["OPENROUTER_API_KEY"] = settings.openrouter_api_key
        updates["OPENROUTER_API_KEY"] = settings.openrouter_api_key
    if req.openrouter_api_key_backup is not None:
        settings.openrouter_api_key_backup = req.openrouter_api_key_backup.strip()
        os.environ["OPENROUTER_API_KEY_BACKUP"] = settings.openrouter_api_key_backup
        updates["OPENROUTER_API_KEY_BACKUP"] = settings.openrouter_api_key_backup
    if req.openrouter_api_key_tertiary is not None:
        settings.openrouter_api_key_tertiary = req.openrouter_api_key_tertiary.strip()
        os.environ["OPENROUTER_API_KEY_TERTIARY"] = settings.openrouter_api_key_tertiary
        updates["OPENROUTER_API_KEY_TERTIARY"] = settings.openrouter_api_key_tertiary
    if req.moonshot_api_key is not None:
        settings.moonshot_api_key = req.moonshot_api_key.strip()
        os.environ["MOONSHOT_API_KEY"] = settings.moonshot_api_key
        updates["MOONSHOT_API_KEY"] = settings.moonshot_api_key
    if req.openai_api_key is not None:
        settings.openai_api_key = req.openai_api_key.strip()
        os.environ["OPENAI_API_KEY"] = settings.openai_api_key
        updates["OPENAI_API_KEY"] = settings.openai_api_key
    if req.anthropic_api_key is not None:
        settings.anthropic_api_key = req.anthropic_api_key.strip()
        os.environ["ANTHROPIC_API_KEY"] = settings.anthropic_api_key
        updates["ANTHROPIC_API_KEY"] = settings.anthropic_api_key
    if req.gemini_api_key is not None:
        settings.gemini_api_key = req.gemini_api_key.strip()
        os.environ["GEMINI_API_KEY"] = settings.gemini_api_key
        updates["GEMINI_API_KEY"] = settings.gemini_api_key
    if req.default_model is not None and req.default_model.strip():
        settings.default_model = req.default_model.strip()
        updates["DEFAULT_MODEL"] = settings.default_model
    if req.mock_llm is not None:
        settings.mock_llm = req.mock_llm
        updates["MOCK_LLM"] = str(req.mock_llm).lower()

    # Persist to .env files
    env_paths = [Path(__file__).parents[3] / ".env", Path(__file__).parents[4] / ".env"]
    for env_path in env_paths:
        if env_path.exists():
            try:
                lines = env_path.read_text(encoding="utf-8").splitlines()
                new_lines = []
                seen_keys = set()
                for line in lines:
                    if "=" in line and not line.strip().startswith("#"):
                        key = line.split("=", 1)[0].strip()
                        if key in updates:
                            new_lines.append(f"{key}={updates[key]}")
                            seen_keys.add(key)
                            continue
                    new_lines.append(line)
                for k, v in updates.items():
                    if k not in seen_keys:
                        new_lines.append(f"{k}={v}")
                env_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
            except Exception as e:
                log.warning("could_not_persist_env", path=str(env_path), error=str(e))

    return {
        "status": "success",
        "message": "API keys successfully updated and loaded into runtime.",
        "settings": await get_settings_keys(),
    }


class KeyTestRequest(BaseModel):
    provider: str
    model: str | None = None


@app.post("/api/settings/test-key", tags=["settings"])
async def test_provider_connection(req: KeyTestRequest) -> dict:
    """Send a lightweight test completion ping to verify the API key is active."""
    from agentflow.core.llm.client import complete

    provider_models = {
        "openrouter": "openrouter/free",
        "moonshot": "moonshot/moonshot-v1-8k",
        "openai": "gpt-4o-mini",
        "anthropic": "claude-3-5-sonnet-20241022",
        "gemini": "gemini/gemini-1.5-flash",
    }
    target_model = req.model or provider_models.get(req.provider.lower(), settings.default_model)

    try:
        resp = await complete(
            messages=[{"role": "user", "content": "Respond with the single word 'READY'"}],
            model=target_model,
            max_tokens=10,
        )
        return {
            "success": True,
            "provider": req.provider,
            "model": target_model,
            "response": resp.content.strip(),
            "latency_tokens": resp.total_tokens,
        }
    except Exception as exc:
        return {
            "success": False,
            "provider": req.provider,
            "model": target_model,
            "error": str(exc),
        }


