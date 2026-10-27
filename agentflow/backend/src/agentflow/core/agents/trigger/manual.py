"""Manual Trigger agent — the entry point for user-initiated workflow runs."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar

from agentflow.core.agents.base import BaseAgent
from agentflow.core.schemas.workflow import (
    AgentMessage,
    AgentType,
    MessageMetadata,
    NodeConfig,
    NodeRunStatus,
)

if TYPE_CHECKING:
    from agentflow.core.executor.context import RunContext
    from agentflow.core.tools.base import BaseTool


class ManualTriggerAgent(BaseAgent):
    """
    Manual Trigger node — passes trigger_data through unchanged.

    No LLM call is made. The trigger just accepts whatever data
    the user provided when starting the run (lead_name, company, goal, etc.)
    and makes it available to downstream nodes.

    Note: In practice the runner pre-seeds trigger node outputs BEFORE
    calling agent.run() via _seed_trigger_outputs(), so this agent may
    not be invoked at all. It's here as a no-op fallback.
    """

    type_key: ClassVar[AgentType] = AgentType.TRIGGER_MANUAL

    async def run(
        self,
        input_data: dict[str, Any],
        config: NodeConfig,
        context: RunContext,
        tools: list[BaseTool],
    ) -> AgentMessage:
        # Find this trigger's node_id from the workflow
        trigger_node_id = "trigger"
        for node in context.workflow.nodes:
            if node.type == AgentType.TRIGGER_MANUAL and node.config == config:
                trigger_node_id = node.id
                break

        return AgentMessage(
            run_id=context.run.id,
            node_id=trigger_node_id,
            status=NodeRunStatus.COMPLETED,
            data=context.run.trigger_data or input_data,
            metadata=MessageMetadata(model="none"),
        )
