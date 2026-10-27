"""
SQLAlchemy ORM models — persistent counterparts of the Pydantic schemas.

Design philosophy:
  - The Pydantic schemas in core/schemas/ remain the SINGLE SOURCE OF TRUTH
    for data shapes. These ORM models exist purely for persistence.
  - WorkflowModel stores the entire WorkflowDef as a JSONB column. This avoids
    an ORM explosion (separate tables for nodes, edges, configs) and makes
    versioning trivial — every save is a snapshot.
  - RunModel and NodeRunModel are normalized tables because we need to query
    runs by status, sort by time, and stream node-level events.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import (
    JSON,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from agentflow.db.engine import Base

JSON_TYPE = JSON().with_variant(JSONB, "postgresql")
UUID_TYPE = Uuid(as_uuid=True).with_variant(PG_UUID(as_uuid=True), "postgresql")


def _utcnow() -> datetime:
    return datetime.now(UTC)


# ═══════════════════════════════════════════════════════════════════════════════
# Workflow (stores the full graph definition as JSONB/JSON)
# ═══════════════════════════════════════════════════════════════════════════════


class WorkflowModel(Base):
    """Persisted workflow definition.

    The `definition` column stores the complete WorkflowDef.model_dump()
    as a JSON/JSONB object. This means:
      - No schema migrations when we add fields to WorkflowDef
      - Full-text search on node labels via JSONB operators
      - Version history is just rows with the same workflow_id but
        different version numbers
    """
    __tablename__ = "workflows"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID_TYPE, primary_key=True, default=uuid.uuid4,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False, default="Untitled Workflow")
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    # The full WorkflowDef serialized as JSON
    definition: Mapped[dict] = mapped_column(JSON_TYPE, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=_utcnow,
    )

    # Relationship: one workflow → many runs
    runs: Mapped[list[RunModel]] = relationship(
        back_populates="workflow", cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("ix_workflows_name", "name"),
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Run (a single execution of a workflow)
# ═══════════════════════════════════════════════════════════════════════════════


class RunModel(Base):
    """Persisted workflow run.

    Status transitions: pending → running → completed|failed|cancelled
    The trigger_data column stores the initial input that started the run.
    """
    __tablename__ = "runs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID_TYPE, primary_key=True, default=uuid.uuid4,
    )
    workflow_id: Mapped[uuid.UUID] = mapped_column(
        UUID_TYPE, ForeignKey("workflows.id", ondelete="CASCADE"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending",
    )
    trigger_data: Mapped[dict] = mapped_column(JSON_TYPE, nullable=False, default=dict)
    shared_context: Mapped[dict] = mapped_column(JSON_TYPE, nullable=False, default=dict)
    total_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_cost_usd: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(),
    )

    # Relationships
    workflow: Mapped[WorkflowModel] = relationship(back_populates="runs")
    node_runs: Mapped[list[NodeRunModel]] = relationship(
        back_populates="run", cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("ix_runs_workflow_id", "workflow_id"),
        Index("ix_runs_status", "status"),
        Index("ix_runs_created_at", "created_at"),
    )


# ═══════════════════════════════════════════════════════════════════════════════
# NodeRun (a single node execution within a run)
# ═══════════════════════════════════════════════════════════════════════════════


class NodeRunModel(Base):
    """Persisted individual node execution record.

    Each row represents one execution attempt of a node within a run.
    Multiple rows per node_id are possible due to retries and feedback loops.
    """
    __tablename__ = "node_runs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID_TYPE, primary_key=True, default=uuid.uuid4,
    )
    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID_TYPE, ForeignKey("runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    node_id: Mapped[str] = mapped_column(String(255), nullable=False)
    agent_type: Mapped[str] = mapped_column(String(50), nullable=False)
    attempt: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    iteration: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    input_data: Mapped[dict] = mapped_column(JSON_TYPE, nullable=False, default=dict)
    output_data: Mapped[dict | None] = mapped_column(JSON_TYPE, nullable=True)
    raw_llm_output: Mapped[str | None] = mapped_column(Text, nullable=True)
    prompt_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cost_usd: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationship
    run: Mapped[RunModel] = relationship(back_populates="node_runs")

    __table_args__ = (
        Index("ix_node_runs_run_id", "run_id"),
        Index("ix_node_runs_node_id", "node_id"),
        Index("ix_node_runs_status", "status"),
    )
