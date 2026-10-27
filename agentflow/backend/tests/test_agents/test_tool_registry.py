"""
Phase 2 tests — Tool Registry.

Tests tool registration, lookup, resolution, and error handling.
"""
from __future__ import annotations

import pytest


class TestToolRegistry:
    @pytest.fixture
    def registry(self):
        """Fresh registry for each test."""
        from agentflow.core.tools.registry import ToolRegistry
        return ToolRegistry()

    @pytest.fixture
    def mock_tool(self):
        """A minimal mock tool for testing."""
        from typing import Any, ClassVar

        from agentflow.core.schemas.tool import ToolResult
        from agentflow.core.tools.base import BaseTool

        class MockTool(BaseTool):
            name: ClassVar[str] = "mock_tool"
            description: ClassVar[str] = "A mock tool for testing"
            parameters_schema: ClassVar[dict] = {
                "type": "object",
                "properties": {"value": {"type": "string"}},
                "required": ["value"],
            }

            async def execute(self, arguments: dict[str, Any]) -> ToolResult:
                return ToolResult(
                    tool_name=self.name,
                    success=True,
                    data={"result": arguments.get("value", "")},
                )

        return MockTool()

    def test_register_and_get(self, registry, mock_tool):
        registry.register(mock_tool)
        retrieved = registry.get("mock_tool")
        assert retrieved is mock_tool

    def test_get_unknown_raises(self, registry):
        from agentflow.core.tools.registry import ToolNotFoundError
        with pytest.raises(ToolNotFoundError):
            registry.get("nonexistent_tool")

    def test_is_registered(self, registry, mock_tool):
        assert not registry.is_registered("mock_tool")
        registry.register(mock_tool)
        assert registry.is_registered("mock_tool")

    def test_list_registered(self, registry, mock_tool):
        assert registry.list_registered() == []
        registry.register(mock_tool)
        assert "mock_tool" in registry.list_registered()

    def test_resolve_tools(self, registry, mock_tool):
        registry.register(mock_tool)
        resolved = registry.resolve_tools(["mock_tool"])
        assert len(resolved) == 1
        assert resolved[0] is mock_tool

    def test_resolve_tools_raises_on_unknown(self, registry):
        from agentflow.core.tools.registry import ToolNotFoundError
        with pytest.raises(ToolNotFoundError):
            registry.resolve_tools(["unknown_tool"])

    def test_resolve_tools_empty_list(self, registry):
        assert registry.resolve_tools([]) == []

    def test_register_overrides(self, registry, mock_tool):
        """Re-registering a tool name replaces the old instance."""
        from typing import Any, ClassVar

        from agentflow.core.schemas.tool import ToolResult
        from agentflow.core.tools.base import BaseTool

        class AnotherMockTool(BaseTool):
            name: ClassVar[str] = "mock_tool"
            description: ClassVar[str] = "Override"
            parameters_schema: ClassVar[dict] = {"type": "object", "properties": {}}

            async def execute(self, arguments: dict[str, Any]) -> ToolResult:
                return ToolResult(tool_name=self.name, success=True)

        another = AnotherMockTool()
        registry.register(mock_tool)
        registry.register(another)
        assert registry.get("mock_tool") is another


class TestBuiltinToolsRegistration:
    """Test that builtin tools can be registered and have correct names."""

    def test_web_search_tool_name(self):
        from agentflow.core.tools.web_search import WebSearchTool
        assert WebSearchTool.name == "web_search"

    def test_http_tool_name(self):
        from agentflow.core.tools.http_tool import HttpTool
        assert HttpTool.name == "http_request"

    def test_email_send_tool_name(self):
        from agentflow.core.tools.email_tool import EmailSendTool
        assert EmailSendTool.name == "email_send"

    def test_all_tools_have_valid_schemas(self):
        """All builtin tools have valid OpenAI tool definitions."""
        from agentflow.core.tools.email_tool import EmailSendTool
        from agentflow.core.tools.http_tool import HttpTool
        from agentflow.core.tools.web_search import WebSearchTool

        for tool_class in [WebSearchTool, HttpTool, EmailSendTool]:
            tool = tool_class()
            ot = tool.to_openai_tool()
            assert ot["type"] == "function"
            assert ot["function"]["name"] == tool.name
            assert "description" in ot["function"]
            assert "parameters" in ot["function"]
