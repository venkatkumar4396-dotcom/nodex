"""
Synthesizer Agent — Multi-node fan-in aggregation and report generation primitive.

Merges multi-branch findings, evaluates consensus, reconciles data points,
and produces executive-grade synthesis reports.
"""
from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any, ClassVar

import structlog

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


class SynthesizerAgent(BaseAgent):
    """Multi-path aggregator and deliverable synthesis primitive."""

    type_key: ClassVar[AgentType] = AgentType.SYNTHESIZER

    async def run(
        self,
        input_data: dict[str, Any],
        config: NodeConfig,
        context: RunContext,
        tools: list[BaseTool],
    ) -> AgentMessage:
        system_prompt = config.system_prompt or (
            "You are a master Synthesizer & Aggregator Agent. "
            "Synthesize all incoming branches, resolve contradictions, highlight key metrics, "
            "and craft a polished, publication-ready final deliverable."
        )

        clean_inputs = {k: v for k, v in input_data.items() if not k.startswith("_")}
        payload_str = json.dumps(clean_inputs, indent=2, ensure_ascii=False) if clean_inputs else "{}"

        messages = [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": (
                    f"Consolidate and synthesize the following merged upstream branch data:\n\n"
                    f"```json\n{payload_str}\n```\n\n"
                    f"Deliver an executive summary and unified final report."
                ),
            },
        ]

        llm_resp = await complete(
            messages=messages,
            model=config.model,
            temperature=0.0,
            max_tokens=4096,
        )

        output_data = {
            "result": llm_resp.content,
            "report": llm_resp.content,
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
