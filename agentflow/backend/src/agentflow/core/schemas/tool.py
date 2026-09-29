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
