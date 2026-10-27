"""
ToolRegistry — the plugin registry for all tool implementations.

Design:
  - Tools are registered by name (string key), not an enum, because tool
    names are user-defined and can come from MCP servers or plugins.
  - Each node gets *only* the tools listed in its config.tools list.
    The executor resolves that list through this registry.
  - Credentials are NOT stored here. They are injected per-execution by the
    CredentialStore using the node's config.credential_ids map.

Phase 2: Web search, HTTP, Email send.
Phase 6: MCP server tool sources added via MCPToolAdapter.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from agentflow.core.tools.base import BaseTool

log = structlog.get_logger(__name__)


class ToolNotFoundError(KeyError):
    """Raised when a tool name has no registered implementation."""


class ToolRegistry:
    """Singleton registry mapping tool_name → BaseTool instance."""

    def __init__(self) -> None:
        self._registry: dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        """Register a tool instance. Tool.name is the lookup key."""
        self._registry[tool.name] = tool
        log.debug("tool_registered", name=tool.name)

    def get(self, name: str) -> BaseTool:
        """
        Get the tool instance for a given name.

        Raises:
            ToolNotFoundError: if no tool is registered with this name.
        """
        tool = self._registry.get(name)
        if tool is None:
            raise ToolNotFoundError(
                f"No tool registered with name '{name}'. "
                f"Registered tools: {list(self._registry)}"
            )
        return tool

    def resolve_tools(self, names: list[str]) -> list[BaseTool]:
        """
        Resolve a list of tool names into BaseTool instances.

        Unknown names raise ToolNotFoundError immediately so configuration
        errors surface before any LLM call is made.
        """
        return [self.get(name) for name in names]

    def list_registered(self) -> list[str]:
        return list(self._registry.keys())

    def is_registered(self, name: str) -> bool:
        return name in self._registry


# Global singleton — used by the executor and node_runner
tool_registry = ToolRegistry()


def register_all_builtin_tools() -> None:
    """
    Import and register all built-in tool implementations.

    Called once at application startup alongside register_all_builtin_agents().
    """
    from agentflow.core.tools.email_tool import EmailSendTool
    from agentflow.core.tools.http_tool import HttpTool
    from agentflow.core.tools.web_search import WebSearchTool

    tool_registry.register(WebSearchTool())
    tool_registry.register(HttpTool())
    tool_registry.register(EmailSendTool())

    log.info(
        "builtin_tools_registered",
        count=len(tool_registry.list_registered()),
        names=tool_registry.list_registered(),
    )
