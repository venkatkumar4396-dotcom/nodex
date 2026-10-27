"""
Memory Agent — persistent state, conversational recall, and entity tracking.

Phase 6: Multi-Turn Memory & State Management.
The Memory agent manages key-value entity states, updates operational memory buffers, and retrieves prior context across steps or sessions.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar

import structlog
from pydantic import BaseModel, Field

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

log = structlog.get_logger(__name__)


class MemoryEntry(BaseModel):
    key: str = Field(description="Memory identifier or entity key")
    value: Any = Field(description="Stored value or fact")
    category: str = Field(default="entity", description="Category: entity, preference, summary, conversation")


class MemoryOutput(BaseModel):
    """Structured output from the Memory agent."""
    action: str = Field(description="Action executed: read, write, search, or merge")
    recalled_memories: dict[str, Any] = Field(default_factory=dict, description="Memories retrieved or updated")
    memory_count: int = Field(default=0, description="Total active memory items tracked")
    status: str = Field(default="synced", description="Memory sync status")


class MemoryAgent(BaseAgent):
    """
    Memory Agent: manages state persistence across steps.

    Expected input fields:
      - action (str, optional): 'read', 'write', 'search' (defaults to 'merge')
      - memory_updates (dict, optional): key-values to store
      - query_keys (list[str], optional): specific keys to recall
    """

    type_key: ClassVar[AgentType] = AgentType.MEMORY

    async def run(
        self,
        input_data: dict[str, Any],
        config: NodeConfig,
        context: RunContext,
        tools: list[BaseTool],
    ) -> AgentMessage:
        action = input_data.get("action", "merge")
        updates = input_data.get("memory_updates") or input_data.get("data") or {}

        # If incoming data has general fields, store them as memory items
        memory_store: dict[str, Any] = context.get_shared("persistent_memory") or {}

        if action in ("write", "merge"):
            for k, v in updates.items():
                if not k.startswith("_"):
                    memory_store[k] = v
            # Also capture key findings from input if present
            for k in ("topic", "lead_name", "company", "goal"):
                if input_data.get(k):
                    memory_store[k] = input_data[k]

            context.set_shared("persistent_memory", memory_store)

        output = MemoryOutput(
            action=action,
            recalled_memories=dict(memory_store),
            memory_count=len(memory_store),
            status="synced",
        )

        return AgentMessage(
            run_id=context.run.id,
            node_id=context.current_node_id or "memory",
            status=NodeRunStatus.COMPLETED,
            input_data=input_data,
            data=output.model_dump(),
            metadata=MessageMetadata(
                prompt_tokens=0,
                completion_tokens=0,
                total_tokens=0,
                cost_usd=0.0,
                model="in-memory-state",
            ),
        )
