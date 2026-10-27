"""
API-specific Pydantic schemas for request/response serialization.

These wrap the core schemas from core/schemas/ for API-specific concerns
(pagination, summaries, timestamps as ISO strings, etc.) while the core
schemas remain the engine's source of truth.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from agentflow.core.schemas.workflow import (
    EdgeDef,
    NodeDef,
)

# ═══════════════════════════════════════════════════════════════════════════════
# Workflow CRUD
# ═══════════════════════════════════════════════════════════════════════════════


class WorkflowCreate(BaseModel):
    """Request body for creating a new workflow."""
    name: str = "Untitled Workflow"
    description: str = ""
    tags: list[str] = Field(default_factory=list)
    status: str = "draft"
    environment: str = "development"
    nodes: list[NodeDef] = Field(default_factory=list)
    edges: list[EdgeDef] = Field(default_factory=list)
    global_max_cost_usd: float | None = None
    global_max_steps: int = 100


class WorkflowUpdate(BaseModel):
    """Request body for updating an existing workflow."""
    name: str | None = None
    description: str | None = None
    tags: list[str] | None = None
    status: str | None = None
    environment: str | None = None
    nodes: list[NodeDef] | None = None
    edges: list[EdgeDef] | None = None
    global_max_cost_usd: float | None = None
    global_max_steps: int | None = None


class WorkflowSummary(BaseModel):
    """Lightweight workflow listing with execution states, tags & topology preview."""
    id: UUID
    name: str
    description: str = ""
    version: int
    tags: list[str] = Field(default_factory=list)
    status: str = "draft"
    environment: str = "development"
    node_count: int
    edge_count: int
    last_run_at: datetime | None = None
    last_run_status: str | None = None
    success_rate: float | None = None
    nodes_preview: list[dict[str, Any]] = Field(default_factory=list)
    edges_preview: list[dict[str, Any]] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class WorkflowDetail(BaseModel):
    """Full workflow detail including graph definition."""
    id: UUID
    name: str
    description: str = ""
    version: int
    tags: list[str] = Field(default_factory=list)
    status: str = "draft"
    environment: str = "development"
    nodes: list[NodeDef]
    edges: list[EdgeDef]
    global_max_cost_usd: float | None
    global_max_steps: int
    created_at: datetime
    updated_at: datetime


# ═══════════════════════════════════════════════════════════════════════════════
# Run
# ═══════════════════════════════════════════════════════════════════════════════


class RunCreate(BaseModel):
    """Request body to trigger a workflow run."""
    trigger_data: dict[str, Any] = Field(default_factory=dict)
    shared_context: dict[str, Any] = Field(default_factory=dict)


class NodeRunOut(BaseModel):
    """API representation of a single node execution."""
    id: UUID
    node_id: str
    agent_type: str
    attempt: int
    iteration: int
    status: str
    input_data: dict[str, Any]
    output_data: dict[str, Any] | None
    prompt_tokens: int
    completion_tokens: int
    cost_usd: float
    duration_ms: int
    error: str | None
    started_at: datetime | None
    completed_at: datetime | None


class RunSummary(BaseModel):
    """Lightweight run listing."""
    id: UUID
    workflow_id: UUID
    status: str
    total_tokens: int
    total_cost_usd: float
    error: str | None
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None


class RunDetail(BaseModel):
    """Full run detail including all node runs."""
    id: UUID
    workflow_id: UUID
    status: str
    trigger_data: dict[str, Any]
    shared_context: dict[str, Any]
    total_tokens: int
    total_cost_usd: float
    error: str | None
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    node_runs: list[NodeRunOut]


# ═══════════════════════════════════════════════════════════════════════════════
# Phase 6 & 7: Human Approval, Generation & Analytics
# ═══════════════════════════════════════════════════════════════════════════════


class ApprovalDecision(BaseModel):
    """Payload to approve or reject a paused workflow run."""
    node_id: str | None = None
    reviewer: str = "user"
    notes: str = ""


class WorkflowGenerateRequest(BaseModel):
    """Request body for AI-generated workflows."""
    prompt: str = Field(..., min_length=3, description="Description of the desired workflow")
    name: str | None = None


class AnalyticsOverview(BaseModel):
    """System-wide telemetry and performance metrics."""
    total_runs: int
    completed_runs: int
    failed_runs: int
    paused_runs: int
    cancelled_runs: int
    success_rate: float
    total_tokens: int
    total_cost_usd: float
    avg_duration_ms: float
    runs_by_status: dict[str, int]
    top_agents: list[dict[str, Any]]
    recent_runs: list[RunSummary]


# ═══════════════════════════════════════════════════════════════════════════════
# Generic API responses
# ═══════════════════════════════════════════════════════════════════════════════


class PaginatedResponse(BaseModel):
    """Generic paginated response wrapper."""
    items: list[Any]
    total: int
    page: int
    page_size: int


class HealthResponse(BaseModel):
    """Health check response."""
    status: str = "ok"
    version: str = "0.1.0"
    database: str = "unknown"


# ═══════════════════════════════════════════════════════════════════════════════
# Batch Operations
# ═══════════════════════════════════════════════════════════════════════════════


class BatchDeleteRequest(BaseModel):
    ids: list[UUID]


class BatchTagRequest(BaseModel):
    ids: list[UUID]
    tags: list[str]
    mode: str = "add"  # "add", "remove", "set"


class BatchStatusRequest(BaseModel):
    ids: list[UUID]
    status: str  # "active", "draft", "failed"


class BatchResponse(BaseModel):
    affected_count: int
    message: str


# ═══════════════════════════════════════════════════════════════════════════════
# One-Click Deployment
# ═══════════════════════════════════════════════════════════════════════════════


class DeployRequest(BaseModel):
    api_key_enabled: bool = True
    environment: str = "production"


class DeployDetail(BaseModel):
    workflow_id: UUID
    workflow_name: str
    endpoint_url: str
    webhook_url: str
    api_key: str
    curl_example: str
    python_example: str
    js_example: str
    widget_snippet: str
    deployed_at: datetime


# ═══════════════════════════════════════════════════════════════════════════════
# Human-in-the-Loop (HITL) Inbox
# ═══════════════════════════════════════════════════════════════════════════════


class PendingApprovalItem(BaseModel):
    run_id: UUID
    workflow_id: UUID
    workflow_name: str
    node_id: str
    node_label: str
    node_type: str
    paused_at: datetime | None
    input_snapshot: dict[str, Any] = Field(default_factory=dict)
    prompt_or_message: str = ""
