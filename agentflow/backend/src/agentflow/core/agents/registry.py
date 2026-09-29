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
        self._registry: dict[AgentType, "BaseAgent"] = {}

    def register(self, agent_type: AgentType, agent: "BaseAgent") -> None:
        """Register an agent instance for an agent type."""
        self._registry[agent_type] = agent
        log.debug("agent_registered", type_key=agent_type.value)

    def get(self, agent_type: AgentType) -> "BaseAgent":
        """
        Get the agent instance for a given type.
        
        Raises:
            AgentNotFoundError: if no agent is registered for this type.
        """
        agent = self._registry.get(agent_type)
        if agent is None:
            raise AgentNotFoundError(
                f"No agent registered for type '{agent_type.value}'. "
                f"Registered types: {[t.value for t in self._registry]}"
            )
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
    # Phase 1 agents
    from agentflow.core.agents.trigger.manual import ManualTriggerAgent
    from agentflow.core.agents.research.research_agent import ResearchAgent
    from agentflow.core.agents.classifier.classifier_agent import ClassifierAgent
    from agentflow.core.agents.writer.writer_agent import WriterAgent
    from agentflow.core.agents.reviewer.reviewer_agent import ReviewerAgent

    agent_registry.register(AgentType.TRIGGER_MANUAL, ManualTriggerAgent())
    agent_registry.register(AgentType.RESEARCH, ResearchAgent())
    agent_registry.register(AgentType.ROUTER, ClassifierAgent())
    agent_registry.register(AgentType.WRITER, WriterAgent())
    agent_registry.register(AgentType.REVIEWER, ReviewerAgent())

    log.info(
        "builtin_agents_registered",
        count=len(agent_registry.list_registered()),
        types=[t.value for t in agent_registry.list_registered()],
    )
