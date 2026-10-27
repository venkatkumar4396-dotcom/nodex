"""
AgentFlow tools package.

Phase 1: BaseTool interface + ToolDef/ToolResult schemas.
Phase 2: WebSearchTool, HttpTool, EmailSendTool + ToolRegistry + CredentialStore + ToolLoop.
"""
from agentflow.core.schemas.tool import ToolDef, ToolResult
from agentflow.core.tools.base import BaseTool

__all__ = ["BaseTool", "ToolDef", "ToolResult"]
