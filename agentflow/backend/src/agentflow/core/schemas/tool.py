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


class ToolExecutionStep(BaseModel):
    """A single step in an agent's reasoning & tool execution trace."""
    round: int
    thought: str | None = None
    tool_name: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    observation: str | None = None
    success: bool = True
    duration_ms: int = 0
    error: str | None = None
    status: str = "completed"  # completed, suggested_only, awaiting_approval, timed_out, duplicate_blocked

