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

# 
# Enums
#


class AgentType(str, Enum):
    """All supported agent/node types.
    
    Adding a new agent = add an entry here + create the class + register it.
    No engine changes required.
    """
    # ── Core Primitives
    TRIGGER_MANUAL = "trigger_manual"
    TRIGGER_WEBHOOK = "trigger_webhook"
    PROMPT = "prompt"
    TOOL = "tool"
    ROUTER = "router"
    HUMAN_APPROVAL = "human_approval"
    CODE = "code"
    SYNTHESIZER = "synthesizer"

    # ── Specialized / Control
    TRIGGER_CRON = "trigger_cron"
    SUPERVISOR = "supervisor"
    LOOP = "loop"

    # ── Information 
    RESEARCH = "research"
    SCRAPER = "scraper"
    RAG = "rag"
    SQL = "sql"
    DOCUMENT_PARSER = "document_parser"
    VECTOR_SEARCH = "vector_search"
    VISION = "vision"

    # ── Processing / creation 
    SUMMARIZER = "summarizer"
    WRITER = "writer"
    TRANSFORMER = "transformer"
    TRANSLATOR = "translator"
    DATA_ANALYST = "data_analyst"
    AUDIO_TRANSCRIBER = "audio_transcriber"

    # ── Quality / safety ─
    REVIEWER = "reviewer"
    VALIDATOR = "validator"
    ERROR_HANDLER = "error_handler"
    GUARDRAIL = "guardrail"

    # ── Action
    EMAIL = "email"
    HTTP_API = "http_api"
    SPREADSHEET = "spreadsheet"
    MESSAGING = "messaging"
    CALENDAR = "calendar"
    FILE = "file"
    CRM = "crm"
    WEBHOOK_DISPATCHER = "webhook_dispatcher"
    GITHUB_OPS = "github_ops"

    # ── Memory
    MEMORY = "memory"

    # ── Protocols & Integrations
    MCP_CLIENT = "mcp_client"
    MCP_SERVER = "mcp_server"

    # ── Advanced Autonomous / Web
    BROWSER_OPERATOR = "browser_operator"


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
    TIMED_OUT = "timed_out"
    AWAITING_APPROVAL = "awaiting_approval"
    APPROVED = "approved"
    REJECTED = "rejected"


# 
# Sub-schemas
# 


class RetryPolicy(BaseModel):
    """Per-node retry configuration."""
    max_attempts: int = Field(default=3, ge=1, le=10)
    backoff_seconds: float = Field(default=1.0, ge=0.0)
    backoff_multiplier: float = Field(default=2.0, ge=1.0)
    # If True, also retry on validation errors (not just network/LLM errors)
    retry_on_validation_error: bool = True


class Position(BaseModel):
    """Canvas x/y position for the React Flow node."""
    x: float = 0.0
    y: float = 0.0


class JoinPolicy(str, Enum):
    WAIT_ALL = "wait_all"  # Wait for all live (non-skipped) incoming edges (default)
    WAIT_ANY = "wait_any"  # Execute as soon as any incoming edge completes


class AutonomyLevel(str, Enum):
    """Autonomy level for agent nodes and workflow execution governance."""
    SUGGEST = "suggest"      # Read-only / Propose actions without executing destructive tools
    ASK_FIRST = "ask_first"  # Destructive actions require human sign-off via HITL
    ACT = "act"              # Fully autonomous execution of tools


class NodeConfig(BaseModel):
    """Per-node configuration: model, prompt, tools, schemas, limits."""
    model: str = "moonshot/moonshot-v1-32k"
    system_prompt: str = ""
    tools: list[str] = Field(default_factory=list)
    credential_ids: dict[str, str] = Field(default_factory=dict)  # tool_name -> cred_id
    input_schema: dict[str, Any] = Field(default_factory=dict)    # JSON Schema
    output_schema: dict[str, Any] = Field(default_factory=dict)   # JSON Schema
    retry_policy: RetryPolicy = Field(default_factory=RetryPolicy)
    timeout_seconds: int = Field(default=60, ge=1)
    max_cost_usd: float | None = None
    max_loop_iterations: int = Field(default=3, ge=1, le=20, description="Max feedback loop iterations")
    join_policy: JoinPolicy = Field(default=JoinPolicy.WAIT_ALL, description="Fan-in join policy: wait_all or wait_any")
    fallback_models: list[str] = Field(default_factory=list, description="Fallback models for self-healing execution")
    autonomy: AutonomyLevel = Field(default=AutonomyLevel.ASK_FIRST, description="Autonomy level: suggest | ask_first | act")
    max_tool_rounds: int = Field(default=10, ge=1, le=50, description="Max tool iterations in agent loop")
    tool_timeout_seconds: float = Field(default=30.0, ge=1.0, le=300.0, description="Per-tool call timeout in seconds")
    # Extra agent-specific config (merged into agent's own config schema)
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
    source: str        # source node_id
    source_handle: str = "default"
    target: str        # target node_id
    target_handle: str = "default"
    # Optional CEL/simple expression evaluated against source output
    # e.g. "output.score >= 7"
    condition: str | None = None
    # Maps target input fields from source output
    # e.g. {"topic": "{{research.output.summary}}"}
    data_map: dict[str, str] = Field(default_factory=dict)
    # Phase 3: Advanced Control Flow
    is_feedback: bool = Field(default=False, description="True if feedback loop / cycle edge")
    is_default: bool = Field(default=False, description="True if default branch when other conditions are false")
    is_error_handler: bool = Field(default=False, description="True if edge routes node execution errors")
    max_iterations: int | None = Field(default=None, description="Max loop iterations override")
    label: str = Field(default="", description="Visual label on canvas")


class WorkflowDef(BaseModel):
    """Complete workflow definition stored as JSON in the database."""
    id: UUID = Field(default_factory=uuid4)
    name: str = "Untitled Workflow"
    description: str = ""
    version: int = 1
    tags: list[str] = Field(default_factory=list)
    status: str = Field(default="draft", description="draft, active, or failed")
    environment: str = Field(default="development", description="development or production")
    nodes: list[NodeDef] = Field(default_factory=list)
    edges: list[EdgeDef] = Field(default_factory=list)
    global_max_cost_usd: float | None = None
    global_max_steps: int = Field(default=100, ge=1)
    global_max_time_seconds: float | None = Field(default=None, ge=1.0, description="Run-level timeout in seconds")
    autonomy: AutonomyLevel | None = Field(default=None, description="Workflow-wide default autonomy level override")

    def get_node(self, node_id: str) -> NodeDef | None:
        return next((n for n in self.nodes if n.id == node_id), None)

    def successors(self, node_id: str) -> list[EdgeDef]:
        return [e for e in self.edges if e.source == node_id]

    def predecessors(self, node_id: str) -> list[str]:
        return [e.source for e in self.edges if e.target == node_id]


# 
# Message envelope — all inter-agent communication uses this shape
# 


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
    """Standard envelope for all inter-agent communication.
    
    Every node produces one of these. The executor uses it to:
      - Update run totals (tokens, cost)
      - Resolve data mappings for downstream nodes
      - Emit WebSocket events (Phase 4+)
      - Persist the node_run record
    """
    run_id: UUID
    node_id: str
    status: NodeRunStatus
    input_data: dict[str, Any] = Field(default_factory=dict)
    data: dict[str, Any] = Field(default_factory=dict)
    metadata: MessageMetadata = Field(default_factory=MessageMetadata)
    errors: list[str] = Field(default_factory=list)


# 
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
    started_at: float | None = None   # Unix timestamp
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
