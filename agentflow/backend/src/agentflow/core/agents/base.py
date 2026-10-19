"""
BaseAgent — the abstract base class every agent must implement.

Design principles:
  1. Agents are stateless. All per-run state lives in RunContext.
     This means agents can be instantiated once and reused across runs.

  2. Each agent class declares its type_key (matches AgentType enum),
     plus optional input/output/config Pydantic models for documentation
     and schema generation.

  3. The only required method is run(). It receives:
     - input_data: resolved from edge data_maps (what this node needs)
     - config: NodeConfig (model, system_prompt, tools, etc.)
     - context: RunContext (shared state, node outputs, limits)
     - tools: list of BaseTool instances assigned to this node

  4. run() MUST return an AgentMessage. If the agent encounters an error
     it can't recover from, it should raise an exception — the node_runner
     will catch it and trigger a retry.

  5. Agents that use LLMs MUST use complete_structured() to ensure their
     output is validated. They should NOT build ad-hoc JSON string parsing.

  6. Prompt injection defense: agents MUST treat all data from tools,
     web pages, or user documents as DATA, never as instructions.
     The system prompt should be self-contained and authoritative.
     Tool results are wrapped in tags like <tool_result>...</tool_result>
     and explicitly framed as external untrusted data.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, ClassVar

from agentflow.core.schemas.workflow import AgentMessage, AgentType, NodeConfig

if TYPE_CHECKING:
    from agentflow.core.executor.context import RunContext
    from agentflow.core.tools.base import BaseTool


class BaseAgent(ABC):
    """
    Abstract base for all AgentFlow agents.

    Class attributes (set on each subclass):
        type_key: The AgentType enum value this class implements.

    Example subclass:

        class SummarizerAgent(BaseAgent):
            type_key = AgentType.SUMMARIZER

            async def run(self, input_data, config, context, tools):
                ...
                return AgentMessage(
                    run_id=context.run.id,
                    node_id=context.current_node_id,  # set by node_runner
                    status=NodeRunStatus.COMPLETED,
                    data=output.model_dump(),
                    metadata=MessageMetadata(
                        prompt_tokens=resp.prompt_tokens,
                        completion_tokens=resp.completion_tokens,
                        total_tokens=resp.total_tokens,
                        cost_usd=resp.cost_usd,
                        model=config.model,
                    ),
                )
    """

    type_key: ClassVar[AgentType]
    allowed_tools: ClassVar[set[str] | None] = None  # None = unrestricted; set = least-privilege allowlist

    @abstractmethod
    async def run(
        self,
        input_data: dict[str, Any],
        config: NodeConfig,
        context: RunContext,
        tools: list[BaseTool],
    ) -> AgentMessage:
        """
        Execute the agent's logic.

        Args:
            input_data: Resolved inputs from upstream nodes (via edge data_maps).
            config: Node configuration (model, system_prompt, tools, etc.).
            context: Run-level shared state.
            tools: Tool instances available to this agent.

        Returns:
            AgentMessage with status, output data, and token/cost metadata.

        Raises:
            Any exception → caught by node_runner for retry logic.
            StructuredOutputError → triggers validation feedback retry.
        """
        ...

    def __init_subclass__(cls, **kwargs: Any) -> None:
        """Validate that subclasses declare type_key."""
        super().__init_subclass__(**kwargs)
        # Skip validation for abstract intermediate classes
        if (
            ABC not in cls.__bases__
            and not getattr(cls, "__abstractmethods__", None)
            and not hasattr(cls, "type_key")
        ):
            raise TypeError(
                f"{cls.__name__} must define `type_key: ClassVar[AgentType]`"
            )
