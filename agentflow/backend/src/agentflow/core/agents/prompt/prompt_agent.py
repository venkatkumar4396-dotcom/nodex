"""
Prompt Agent — Primary LLM reasoning and persona execution primitive.

Executes direct system prompts, roles, directives, and structured reasoning
over arbitrary upstream payloads with Pydantic validation and token tracking.
"""
from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any, ClassVar

import structlog
from pydantic import BaseModel, Field

from agentflow.core.agents.base import BaseAgent
from agentflow.core.llm.client import complete
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


class PromptOutput(BaseModel):
    """Standardized validated output from a Prompt Agent."""
    content: str = Field(description="Primary textual or markdown deliverable response")
    reasoning: str | None = Field(default=None, description="Step-by-step reasoning or thought process")
    status: str = Field(default="completed", description="Status code of the completion")
    extracted_data: dict[str, Any] = Field(default_factory=dict, description="Structured key-value entities or parsed data")


class PromptAgent(BaseAgent):
    """Core Prompt / LLM Reasoning Agent primitive."""

    type_key: ClassVar[AgentType] = AgentType.PROMPT

    async def run(
        self,
        input_data: dict[str, Any],
        config: NodeConfig,
        context: RunContext,
        tools: list[BaseTool],
    ) -> AgentMessage:
        system_prompt = config.system_prompt or (
            "You are an expert autonomous reasoning agent in an AgentFlow DAG workflow. "
            "Analyze the given input data with high precision, synthesize key insights, "
            "and deliver a comprehensive, structured response."
        )

        # Sanitize payload for prompt inclusion
        clean_inputs = {k: v for k, v in input_data.items() if not k.startswith("_")}
        payload_str = json.dumps(clean_inputs, indent=2, ensure_ascii=False) if clean_inputs else "{}"

        messages = [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": (
                    f"Process the following input context payload:\n\n"
                    f"```json\n{payload_str}\n```\n\n"
                    f"Execute your assigned task accurately. Return your findings or output clearly."
                ),
            },
        ]

        llm_resp = await complete(
            messages=messages,
            model=config.model,
            temperature=0.0,
            max_tokens=4096,
        )

        # Structure the payload
        output_data = {
            "result": llm_resp.content,
            "content": llm_resp.content,
            "status": "completed",
            **clean_inputs,
        }

        return AgentMessage(
            run_id=context.run.id,
            node_id=context.current_node_id or self.type_key.value,
            status=NodeRunStatus.COMPLETED,
            data=output_data,
            metadata=MessageMetadata(
                prompt_tokens=llm_resp.prompt_tokens,
                completion_tokens=llm_resp.completion_tokens,
                total_tokens=llm_resp.total_tokens,
                cost_usd=llm_resp.cost_usd,
                model=llm_resp.model,
            ),
        )
