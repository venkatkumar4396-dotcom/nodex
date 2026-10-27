"""
AgentRegistry — the plugin registry for all agent types.

Design: This is the single boundary point between the executor and the
agents. The executor never imports agent classes directly. It only calls:
    agent = agent_registry.get(AgentType.RESEARCH)
    message = await agent.run(...)

This means:
  - Adding a new agent = register it here, zero engine changes
  - Testing the executor = mock the registry
  - Future plugin loading = scan a directory, import, auto-register

The registry holds singleton instances (agents are stateless).
"""
from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from agentflow.core.schemas.workflow import AgentType

if TYPE_CHECKING:
    from agentflow.core.agents.base import BaseAgent

log = structlog.get_logger(__name__)


class AgentNotFoundError(KeyError):
    """Raised when an agent type has no registered implementation."""


class AgentRegistry:
    """Singleton registry mapping AgentType → BaseAgent instance."""

    def __init__(self) -> None:
        self._registry: dict[AgentType, BaseAgent] = {}

    def register(self, agent_type: AgentType, agent: BaseAgent) -> None:
        """Register an agent instance for an agent type."""
        self._registry[agent_type] = agent
        log.debug("agent_registered", type_key=agent_type.value)

    def get(self, agent_type: AgentType) -> BaseAgent:
        """
        Get the agent instance for a given type.
        If no builtins are registered yet, auto-registers them.
        If this specific agent_type has no custom class, provides a UniversalAgent.
        """
        if not self._registry:
            register_all_builtin_agents()

        agent = self._registry.get(agent_type)
        if agent is None:
            # Provide dynamic UniversalAgent fallback for unspecialized types
            from agentflow.core.agents.universal import UniversalAgent
            agent = UniversalAgent(agent_type)
            self._registry[agent_type] = agent
            log.info("universal_agent_assigned", agent_type=agent_type.value)

        return agent

    def list_registered(self) -> list[AgentType]:
        return list(self._registry.keys())

    def is_registered(self, agent_type: AgentType) -> bool:
        return agent_type in self._registry


# Global singleton — used by the executor
agent_registry = AgentRegistry()


def register_all_builtin_agents() -> None:
    """
    Import and register all built-in agent implementations.

    Called once at application startup (main.py or run_demo.py).
    Order doesn't matter — agents are stateless singletons.
    """
    # ── Core Primitives
    from agentflow.core.agents.approval.approval_agent import HumanApprovalAgent
    from agentflow.core.agents.classifier.classifier_agent import ClassifierAgent
    from agentflow.core.agents.code.code_agent import CodeAgent
    from agentflow.core.agents.prompt.prompt_agent import PromptAgent
    from agentflow.core.agents.synthesizer.synthesizer_agent import SynthesizerAgent
    from agentflow.core.agents.tool.tool_agent import ToolAgent
    from agentflow.core.agents.trigger.manual import ManualTriggerAgent

    agent_registry.register(AgentType.TRIGGER_MANUAL, ManualTriggerAgent())
    agent_registry.register(AgentType.PROMPT, PromptAgent())
    agent_registry.register(AgentType.TOOL, ToolAgent())
    agent_registry.register(AgentType.ROUTER, ClassifierAgent())
    agent_registry.register(AgentType.HUMAN_APPROVAL, HumanApprovalAgent())
    agent_registry.register(AgentType.CODE, CodeAgent())
    agent_registry.register(AgentType.SYNTHESIZER, SynthesizerAgent())

    # ── Specialized / Legacy Compatible Implementations
    from agentflow.core.agents.email.email_agent import EmailAgent
    from agentflow.core.agents.memory.memory_agent import MemoryAgent
    from agentflow.core.agents.rag.rag_agent import RAGAgent
    from agentflow.core.agents.research.research_agent import ResearchAgent
    from agentflow.core.agents.reviewer.reviewer_agent import ReviewerAgent
    from agentflow.core.agents.supervisor.supervisor_agent import SupervisorAgent
    from agentflow.core.agents.writer.writer_agent import WriterAgent

    agent_registry.register(AgentType.RESEARCH, ResearchAgent())
    agent_registry.register(AgentType.WRITER, WriterAgent())
    agent_registry.register(AgentType.REVIEWER, ReviewerAgent())
    agent_registry.register(AgentType.EMAIL, EmailAgent())
    agent_registry.register(AgentType.SUPERVISOR, SupervisorAgent())
    agent_registry.register(AgentType.RAG, RAGAgent())
    agent_registry.register(AgentType.MEMORY, MemoryAgent())

    # ── Protocols & Integrations
    from agentflow.core.agents.mcp.mcp_agent import MCPClientAgent
    agent_registry.register(AgentType.MCP_CLIENT, MCPClientAgent())

    # ── Advanced Autonomous / Web
    from agentflow.core.agents.browser.browser_agent import BrowserOperatorAgent
    agent_registry.register(AgentType.BROWSER_OPERATOR, BrowserOperatorAgent())

    log.info(
        "builtin_agents_registered",
        count=len(agent_registry.list_registered()),
        types=[t.value for t in agent_registry.list_registered()],
    )


def register_all_builtin_tools() -> None:
    """
    Import and register all built-in tools. Separate from agents so tools
    can be registered independently (useful in tests).
    """
    from agentflow.core.tools.registry import register_all_builtin_tools as _register
    _register()
