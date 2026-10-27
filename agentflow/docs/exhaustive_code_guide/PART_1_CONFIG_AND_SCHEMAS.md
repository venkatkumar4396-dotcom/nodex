# Part 1: Configuration, Logging & Core Pydantic Schemas
## Exhaustive Code & Line-by-Line Architectural Guide

---

## 1. `src/agentflow/config.py`

### 1.1 Complete Source Code
```python
"""
AgentFlow settings loaded from environment variables.
Uses pydantic-settings for type-safe, documented config.
"""
from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── LLM providers ────────────────────────────────────────────────────────
    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    anthropic_api_key: str = Field(default="", alias="ANTHROPIC_API_KEY")
    gemini_api_key: str = Field(default="", alias="GEMINI_API_KEY")

    # Kimi / Moonshot AI — use prefix "moonshot/" in model names
    # e.g. moonshot/moonshot-v1-32k, moonshot/kimi-k2.5
    moonshot_api_key: str = Field(default="", alias="MOONSHOT_API_KEY")

    # Default model used by agents when no model is specified in node config.
    default_model: str = Field(default="moonshot/moonshot-v1-32k", alias="DEFAULT_MODEL")

    # ── Database (Phase 4+) ───────────────────────────────────────────────────
    database_url: str = Field(
        default="postgresql+asyncpg://agentflow:agentflow@localhost:5432/agentflow",
        alias="DATABASE_URL",
    )

    # ── Redis / Arq (Phase 4+) ────────────────────────────────────────────────
    redis_url: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL")

    # ── Security ──────────────────────────────────────────────────────────────
    secret_key: str = Field(default="CHANGE_ME_IN_PRODUCTION", alias="SECRET_KEY")
    fernet_key: str = Field(default="", alias="FERNET_KEY")

    # ── Execution limits ──────────────────────────────────────────────────────
    default_node_timeout_seconds: int = Field(default=120, alias="DEFAULT_NODE_TIMEOUT_SECONDS")
    default_max_steps: int = Field(default=100, alias="DEFAULT_MAX_STEPS")
    default_max_cost_usd: float = Field(default=5.0, alias="DEFAULT_MAX_COST_USD")

    # ── Logging ───────────────────────────────────────────────────────────────
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    log_format: str = Field(default="console", alias="LOG_FORMAT")  # "json" | "console"


settings = Settings()
```

### 1.2 Line-by-Line Breakdown & Explanation
- **Lines 5**: `from __future__ import annotations` enables PEP 563 postponed evaluation of annotations. Allows type hints to refer to types declared later without circular import errors.
- **Lines 7–8**: `from pydantic import Field` and `from pydantic_settings import BaseSettings, SettingsConfigDict` import Pydantic v2's dedicated settings management package.
- **Lines 11–16**: `class Settings(BaseSettings)` declares the configuration class. `model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")` instructs Pydantic to read environment variables from `.env`, encode in UTF-8, and ignore extra variables not defined in this class (preventing crashes when other system environment variables exist).
- **Lines 19–25**: Strongly typed string fields for `openai_api_key`, `anthropic_api_key`, `gemini_api_key`, and `moonshot_api_key`. Using `alias="OPENAI_API_KEY"` allows the Python attribute name to follow PEP 8 snake_case (`openai_api_key`) while reading from standard uppercase POSIX environment variables.
- **Lines 34**: `default_model` defines the baseline LLM provider string. Defaulted to `moonshot/moonshot-v1-32k` (Kimi), compatible with LiteLLM.
- **Lines 37–43**: Database and Redis connection strings for Phase 4. `postgresql+asyncpg://` declares the async SQLAlchemy engine URL; `redis://localhost:6379/0` sets up the Arq task queue address.
- **Lines 46–47**: `secret_key` provides the master encryption secret used to derive Fernet cryptographic keys in `CredentialStore`. `fernet_key` allows explicit base64 32-byte key injection.
- **Lines 50–52**: `default_node_timeout_seconds` (120s), `default_max_steps` (100 steps), and `default_max_cost_usd` ($5.00) enforce strict platform safety limits to prevent runaway LLM costs or hanging API requests.
- **Lines 55–56**: Logging level and formatting (`"json"` for production, `"console"` for local development).
- **Line 59**: `settings = Settings()` creates the global configuration singleton.

### 1.3 Why We Built This Instead of Alternatives
- **Why `pydantic-settings` instead of `os.getenv` or `python-dotenv`?**  
  Plain `os.getenv()` provides no type conversion (everything is a string, e.g. `"120"` instead of `120`), no schema validation, and silently fails when variables are missing or misconfigured. `BaseSettings` validates types at application startup, rejecting invalid configurations before any workflow executes.
- **Why `extra="ignore"`?**  
  In containerized Docker and Kubernetes deployments, platforms inject many environment variables (e.g. `KUBERNETES_SERVICE_HOST`). Without `extra="ignore"`, Pydantic would raise a `ValidationError` on startup.

---

## 2. `src/agentflow/logging_config.py`

### 2.1 Complete Source Code
```python
"""Structured logging setup using structlog."""
from __future__ import annotations

import logging
import sys

import structlog

from agentflow.config import settings


def configure_logging() -> None:
    """Configure structlog with JSON or console output based on settings."""
    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
    ]

    if settings.log_format == "json":
        renderer: structlog.types.Processor = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer(colors=True)

    structlog.configure(
        processors=shared_processors + [renderer],
        wrapper_class=structlog.make_filtering_bound_logger(
            logging.getLevelName(settings.log_level)
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
        cache_logger_on_first_use=True,
    )


# Configure on import so any module can do `log = structlog.get_logger()`
configure_logging()
```

### 2.2 Line-by-Line Breakdown & Explanation
- **Lines 14–19**: `shared_processors` defines the pipeline of log record transformations:
  - `merge_contextvars`: Pulls async context variables (such as active `run_id` or `node_id`) automatically into every log call across coroutines without manual passing.
  - `add_log_level`: Appends `level="info"`, `level="error"`, etc.
  - `TimeStamper(fmt="iso")`: Formats timestamps in ISO-8601 (`2026-10-01T01:00:00.000000Z`) for precise event sequencing.
  - `StackInfoRenderer`: Formats exception tracebacks cleanly.
- **Lines 21–24**: Dynamic renderer selection:
  - If `settings.log_format == "json"`: Uses `JSONRenderer()` to output machine-readable JSON lines for Datadog or CloudWatch.
  - Otherwise: Uses `ConsoleRenderer(colors=True)` for ANSI-colorized, readable developer output.
- **Lines 26–34**: `structlog.configure`:
  - `wrapper_class=structlog.make_filtering_bound_logger(...)`: Filters out logs below the configured log level before any processor runs, achieving near-zero overhead for suppressed log levels.
  - `logger_factory=structlog.PrintLoggerFactory(file=sys.stdout)`: Writes directly to standard output without blocking Python's global logging lock.
  - `cache_logger_on_first_use=True`: Reuses configured loggers for maximum performance in high-throughput workflows.
- **Line 38**: `configure_logging()` is executed on module import, ensuring structured logging is active immediately across all modules.

### 2.3 Why We Built This Instead of Alternatives
- **Why `structlog` instead of Python's standard `logging`?**  
  Standard `logging` uses string interpolation (`log.info("Node %s finished", node_id)`), which makes log indexing in modern observability platforms (Elasticsearch, Datadog) cumbersome and fragile. `structlog` treats log events as structured key-value dictionaries (`log.info("node_completed", node_id=node.id, cost_usd=0.002, duration_ms=45)`), enabling real-time filtering, metric extraction, and tracing.

---

## 3. `src/agentflow/core/schemas/tool.py`

### 3.1 Complete Source Code
```python
"""Tool schemas — defines the interface every tool must implement."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ToolDef(BaseModel):
    """Declarative definition of a tool (used for LLM function-calling schemas)."""
    name: str
    description: str
    parameters: dict[str, Any] = Field(description="JSON Schema for tool arguments")


class ToolResult(BaseModel):
    """Standardized result returned by every tool execution."""
    tool_name: str
    success: bool
    data: Any = None
    error: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
```

### 3.2 Line-by-Line Breakdown & Explanation
- **Lines 9–13**: `class ToolDef(BaseModel)` defines the declarative metadata contract for an LLM tool.
  - `name: str`: Tool identifier (e.g. `"web_search"`, `"email_send"`).
  - `description: str`: Natural language instructions telling the LLM when and how to call the tool.
  - `parameters: dict[str, Any]`: Standard JSON Schema defining the expected arguments and types.
- **Lines 16–22**: `class ToolResult(BaseModel)` is the standardized envelope returned by any tool execution.
  - `tool_name: str`: Identifier of the tool that ran.
  - `success: bool`: True if the external call succeeded, False on failure.
  - `data: Any`: Structured output payload (dict, list, string, etc.).
  - `error: str | None`: Error description if `success is False`.
  - `metadata: dict[str, Any]`: Execution telemetry such as HTTP status codes, latency in milliseconds, or backend details.

### 3.3 Why We Built This Instead of Alternatives
- **Why decouple `ToolDef` and `ToolResult` from specific vendor formats?**  
  OpenAI uses `{"type": "function", "function": {...}}`; Anthropic uses `{"name": ..., "input_schema": {...}}`; Google Gemini uses `FunctionDeclaration`. By maintaining a vendor-agnostic Pydantic schema, AgentFlow translates tools into any vendor's format cleanly in `BaseTool.to_openai_tool()` without coupling tool authors to a single LLM vendor.

---

## 4. `src/agentflow/core/schemas/workflow.py`

### 4.1 Complete Source Code
```python
"""Core Pydantic schemas — the single source of truth for all data shapes.

These schemas are used by:
  - The executor engine (no FastAPI deps)
  - The FastAPI API (serialization / deserialization)
  - OpenAPI generation → TypeScript type generation (Phase 5)

Design principle: every cross-agent message uses AgentMessage as the envelope.
"""
from __future__ import annotations

from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

# ─────────────────────────────────────────────────────────────────────────────
# Enums
# ─────────────────────────────────────────────────────────────────────────────


class AgentType(str, Enum):
    """All supported agent/node types."""
    # Control / routing
    TRIGGER_MANUAL = "trigger_manual"
    TRIGGER_WEBHOOK = "trigger_webhook"
    TRIGGER_CRON = "trigger_cron"
    SUPERVISOR = "supervisor"
    ROUTER = "router"
    LOOP = "loop"
    HUMAN_APPROVAL = "human_approval"

    # Information
    RESEARCH = "research"
    SCRAPER = "scraper"
    RAG = "rag"
    SQL = "sql"

    # Processing / creation
    SUMMARIZER = "summarizer"
    WRITER = "writer"
    TRANSFORMER = "transformer"
    CODE = "code"
    TRANSLATOR = "translator"

    # Quality / safety
    REVIEWER = "reviewer"
    VALIDATOR = "validator"
    ERROR_HANDLER = "error_handler"

    # Action
    EMAIL = "email"
    HTTP_API = "http_api"
    SPREADSHEET = "spreadsheet"
    MESSAGING = "messaging"
    CALENDAR = "calendar"
    FILE = "file"
    CRM = "crm"

    # Memory
    MEMORY = "memory"


class RunStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class NodeRunStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    AWAITING_APPROVAL = "awaiting_approval"
    APPROVED = "approved"
    REJECTED = "rejected"


# ─────────────────────────────────────────────────────────────────────────────
# Sub-schemas
# ─────────────────────────────────────────────────────────────────────────────


class RetryPolicy(BaseModel):
    """Per-node retry configuration."""
    max_attempts: int = Field(default=3, ge=1, le=10)
    backoff_seconds: float = Field(default=1.0, ge=0.0)
    backoff_multiplier: float = Field(default=2.0, ge=1.0)
    retry_on_validation_error: bool = True


class Position(BaseModel):
    """Canvas x/y position for the React Flow node."""
    x: float = 0.0
    y: float = 0.0


class JoinPolicy(str, Enum):
    WAIT_ALL = "wait_all"  # Wait for all live (non-skipped) incoming edges (default)
    WAIT_ANY = "wait_any"  # Execute as soon as any incoming edge completes


class NodeConfig(BaseModel):
    """Per-node configuration: model, prompt, tools, schemas, limits."""
    model: str = "moonshot/moonshot-v1-32k"
    system_prompt: str = ""
    tools: list[str] = Field(default_factory=list)
    credential_ids: dict[str, str] = Field(default_factory=dict)
    input_schema: dict[str, Any] = Field(default_factory=dict)
    output_schema: dict[str, Any] = Field(default_factory=dict)
    retry_policy: RetryPolicy = Field(default_factory=RetryPolicy)
    timeout_seconds: int = Field(default=60, ge=1)
    max_cost_usd: float | None = None
    max_loop_iterations: int = Field(default=3, ge=1, le=20, description="Max feedback loop iterations")
    join_policy: JoinPolicy = Field(default=JoinPolicy.WAIT_ALL, description="Fan-in join policy: wait_all or wait_any")
    extra: dict[str, Any] = Field(default_factory=dict)


class NodeDef(BaseModel):
    """A single node in the workflow graph."""
    id: str = Field(description="Stable node ID, unique within a workflow")
    type: AgentType
    label: str
    config: NodeConfig = Field(default_factory=NodeConfig)
    position: Position = Field(default_factory=Position)


class EdgeDef(BaseModel):
    """Directed edge connecting two nodes, with optional condition and data mapping."""
    id: str
    source: str
    source_handle: str = "default"
    target: str
    target_handle: str = "default"
    condition: str | None = None
    data_map: dict[str, str] = Field(default_factory=dict)
    is_feedback: bool = Field(default=False, description="True if feedback loop / cycle edge")
    is_default: bool = Field(default=False, description="True if default branch when other conditions are false")
    is_error_handler: bool = Field(default=False, description="True if edge routes node execution errors")
    max_iterations: int | None = Field(default=None, description="Max loop iterations override")
    label: str = Field(default="", description="Visual label on canvas")


class WorkflowDef(BaseModel):
    """Complete workflow definition stored as JSON in the database."""
    id: UUID = Field(default_factory=uuid4)
    name: str = "Untitled Workflow"
    version: int = 1
    nodes: list[NodeDef] = Field(default_factory=list)
    edges: list[EdgeDef] = Field(default_factory=list)
    global_max_cost_usd: float | None = None
    global_max_steps: int = Field(default=100, ge=1)

    def get_node(self, node_id: str) -> NodeDef | None:
        return next((n for n in self.nodes if n.id == node_id), None)

    def successors(self, node_id: str) -> list[EdgeDef]:
        return [e for e in self.edges if e.source == node_id]

    def predecessors(self, node_id: str) -> list[str]:
        return [e.source for e in self.edges if e.target == node_id]


# ─────────────────────────────────────────────────────────────────────────────
# Message envelope — all inter-agent communication uses this shape
# ─────────────────────────────────────────────────────────────────────────────


class MessageMetadata(BaseModel):
    """Token/cost/latency metadata attached to every agent message."""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cost_usd: float = 0.0
    latency_ms: int = 0
    model: str = ""
    attempt: int = 1


class AgentMessage(BaseModel):
    """Standard envelope for all inter-agent communication."""
    run_id: UUID
    node_id: str
    status: NodeRunStatus
    data: dict[str, Any] = Field(default_factory=dict)
    metadata: MessageMetadata = Field(default_factory=MessageMetadata)
    errors: list[str] = Field(default_factory=list)


# ─────────────────────────────────────────────────────────────────────────────
# Run-level records (used by both the in-memory executor and DB models)
# ─────────────────────────────────────────────────────────────────────────────


class NodeRunRecord(BaseModel):
    """In-memory record of a single node execution attempt."""
    run_id: UUID
    node_id: str
    agent_type: AgentType
    attempt: int = 1
    iteration: int = Field(default=1, ge=1, description="Iteration number in loop/feedback execution")
    status: NodeRunStatus = NodeRunStatus.PENDING
    input: dict[str, Any] = Field(default_factory=dict)
    output: dict[str, Any] | None = None
    raw_llm_output: str | None = None
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cost_usd: float = 0.0
    duration_ms: int = 0
    error: str | None = None
    validation_errors: list[str] = Field(default_factory=list)
    started_at: float | None = None
    completed_at: float | None = None


class RunRecord(BaseModel):
    """In-memory record of a full workflow run."""
    id: UUID = Field(default_factory=uuid4)
    workflow_id: UUID
    workflow_version: int = 1
    status: RunStatus = RunStatus.PENDING
    trigger_data: dict[str, Any] = Field(default_factory=dict)
    shared_context: dict[str, Any] = Field(default_factory=dict)
    total_tokens: int = 0
    total_cost_usd: float = 0.0
    node_runs: list[NodeRunRecord] = Field(default_factory=list)
    error: str | None = None
    started_at: float | None = None
    completed_at: float | None = None
```

### 4.2 Line-by-Line Breakdown & Explanation
- **Lines 23–67**: `AgentType(str, Enum)` defines all agent types categorized by purpose (Control, Information, Creation, QA, Action, Memory). Subclassing `str, Enum` allows instances to serialize directly as strings in JSON payloads.
- **Lines 69–87**: `RunStatus` and `NodeRunStatus` track the finite state machines of the workflow and individual nodes. `NodeRunStatus.SKIPPED` is essential for Dead-Path Elimination; `AWAITING_APPROVAL`, `APPROVED`, `REJECTED` enable human-in-the-loop nodes.
- **Lines 94–101**: `RetryPolicy`: Configures retry attempts with exponential backoff:
  $$\text{backoff} = \text{backoff\_seconds} \times (\text{backoff\_multiplier})^{\text{attempt} - 1}$$
  `retry_on_validation_error=True` allows re-prompting the LLM with its JSON schema validation errors to correct its formatting.
- **Lines 103–107**: `Position` stores `x` and `y` coordinates for direct React Flow UI positioning.
- **Lines 109–112**: `JoinPolicy` defines fan-in behavior:
  - `WAIT_ALL`: Node waits until all incoming active edges have resolved.
  - `WAIT_ANY`: Node runs as soon as any incoming edge finishes (first-responder pattern).
- **Lines 114–129**: `NodeConfig`: Complete configuration for an agent node. `credential_ids` maps `{tool_name: credential_id}`. `max_loop_iterations=3` bounds cyclical self-healing iterations.
- **Lines 131–138**: `NodeDef`: Defines a node in the workflow graph with stable `id`, `type`, `label`, `config`, and `position`.
- **Lines 140–159**: `EdgeDef`: The edge model with advanced Phase 3 routing flags:
  - `condition`: String expression (e.g. `output.score >= 7`).
  - `data_map`: Input field remapping dictionary (e.g. `{"topic": "{{research.output.summary}}"}`).
  - `is_feedback`: Marks back-edges for loop execution, excluded from static forward DAG cycle validation.
  - `is_default`: Fallback branch when all other conditional branches evaluate to `False`.
  - `is_error_handler`: Activated only if the source node fails all retries.
- **Lines 161–180**: `WorkflowDef`: Complete workflow graph containing `nodes` and `edges`, with helper query methods `get_node()`, `successors()`, and `predecessors()`.
- **Lines 186–212**: `AgentMessage` & `MessageMetadata`: The unified data envelope passed between all nodes. Tracks exact tokens consumed (`prompt_tokens`, `completion_tokens`), cost in USD (`cost_usd`), and latency in milliseconds.
- **Lines 219–254**: `NodeRunRecord` & `RunRecord`: Audit logs capturing every node run attempt, iteration number, start/end timestamps, inputs, outputs, and errors.

### 4.3 Why We Built This Instead of Alternatives
- **Why a unified `AgentMessage` envelope?**  
  In many agent frameworks (e.g. AutoGen, CrewAI), agents pass raw strings or ad-hoc dictionaries. When a node fails or produces invalid JSON, downstream nodes fail cryptically. `AgentMessage` standardizes status, data, metadata, and error arrays, allowing the runner to detect errors, track token expenditures accurately, and propagate data deterministically.
- **Why Pydantic models as the single source of truth?**  
  In Phase 5, running `npx openapi-typescript` against our FastAPI `/openapi.json` will automatically generate 100% type-safe TypeScript interfaces for React Flow. Frontend and backend share an identical data contract.
