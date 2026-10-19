"""
BaseTool — the interface every tool must implement.

Design:
  - Tools are callable units with a typed argument schema (JSON Schema)
  - Agents only receive tools assigned to them (least privilege)
  - MCP servers are adapted into this interface via MCPAdapter
  - Credentials are injected at execution time — never hardcoded

In Phase 2, real tools (web_search, http_tool, email_tool) will be built.
In Phase 1, this module just defines the interface.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, ClassVar

from agentflow.core.schemas.tool import ToolDef, ToolResult


class BaseTool(ABC):
    """Abstract base for all AgentFlow tools."""

    name: ClassVar[str]
    description: ClassVar[str]
    parameters_schema: ClassVar[dict[str, Any]]  # JSON Schema
    is_destructive: ClassVar[bool] = False

    @abstractmethod
    async def execute(self, arguments: dict[str, Any]) -> ToolResult:
        """
        Execute the tool with the given arguments.

        Args:
            arguments: Dict matching the parameters_schema.

        Returns:
            ToolResult with success/failure + data.

        Security: Never log or include credentials in ToolResult.
        Tool output should be treated as untrusted external data.
        """
        ...

    def to_def(self) -> ToolDef:
        """Convert to ToolDef for LLM function-calling schema."""
        return ToolDef(
            name=self.name,
            description=self.description,
            parameters=self.parameters_schema,
        )

    def to_openai_tool(self) -> dict[str, Any]:
        """OpenAI/LiteLLM tool definition format."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters_schema,
            },
        }
