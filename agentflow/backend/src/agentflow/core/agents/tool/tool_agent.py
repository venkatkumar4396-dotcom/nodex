"""
Tool Agent — Autonomous multi-turn tool-calling agent primitive.

Equipped with attached tools (web search, HTTP REST APIs, email send, etc.),
it reasons iteratively: calls tools, observes external results, and synthesizes answers.
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
from agentflow.core.tools.tool_loop import run_tool_loop

if TYPE_CHECKING:
    from agentflow.core.executor.context import RunContext
    from agentflow.core.tools.base import BaseTool

log = structlog.get_logger(__name__)


class ToolAgent(BaseAgent):
    """Autonomous tool-calling loop primitive."""

    type_key: ClassVar[AgentType] = AgentType.TOOL

    async def run(
        self,
        input_data: dict[str, Any],
        config: NodeConfig,
        context: RunContext,
        tools: list[BaseTool],
    ) -> AgentMessage:
        system_prompt = config.system_prompt or (
            "You are an autonomous tool-enabled agent in an AgentFlow workflow. "
            "Use your attached tools to gather verified data, inspect external endpoints, "
            "and accomplish the objective. Provide a clear, factual, structured deliverable."
        )

        clean_inputs = {k: v for k, v in input_data.items() if not k.startswith("_")}
        payload_str = json.dumps(clean_inputs, indent=2, ensure_ascii=False) if clean_inputs else "{}"

        messages = [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": (
                    f"Execute your objective with the following input data:\n\n"
                    f"```json\n{payload_str}\n```\n\n"
                    f"Call your tools as needed, analyze results, and report back."
                ),
            },
        ]

        # If tools are attached, run the autonomous multi-turn tool loop!
        if tools:
            log.info("tool_agent_executing_loop", tool_count=len(tools), tool_names=[t.name for t in tools])
            loop_result = await run_tool_loop(
                messages=messages,
                tools=tools,
                model=config.model,
                max_rounds=getattr(config, "max_tool_rounds", 10),
                tool_timeout_seconds=getattr(config, "tool_timeout_seconds", 30.0),
                max_cost_usd=config.max_cost_usd,
                autonomy=getattr(config, "autonomy", None),
                context=context,
                node_id=context.current_node_id,
            )

            if loop_result.awaiting_approval:
                log.info("tool_agent_awaiting_approval", node_id=context.current_node_id)
                return AgentMessage(
                    run_id=context.run.id,
                    node_id=context.current_node_id or self.type_key.value,
                    status=NodeRunStatus.AWAITING_APPROVAL,
                    data={
                        "summary": "Execution paused awaiting human approval for destructive action.",
                        "pending_approval": context.get_shared(f"pending_approval_{context.current_node_id}"),
                        "tool_trace": [s.model_dump() for s in loop_result.trace],
                        **clean_inputs,
                    },
                    metadata=MessageMetadata(
                        prompt_tokens=loop_result.total_prompt_tokens,
                        completion_tokens=loop_result.total_completion_tokens,
                        total_tokens=loop_result.total_tokens,
                        cost_usd=loop_result.total_cost_usd,
                        model=config.model or "default",
                    ),
                )

            final_content = ""
            for m in reversed(loop_result.messages):
                if m.get("role") == "assistant" and m.get("content"):
                    final_content = m.get("content")
                    break
            if not final_content and loop_result.tool_results:
                final_content = f"Successfully executed {len(loop_result.tool_results)} tool operations."

            output_data = {
                "result": final_content,
                "content": final_content,
                "tool_calls_count": len(loop_result.tool_results),
                "tool_calls": [
                    {"tool": tr.tool_name, "success": tr.success, "data": tr.data, "error": tr.error}
                    for tr in loop_result.tool_results
                ],
                "tool_trace": [s.model_dump() for s in loop_result.trace],
                "status": "completed",
                **clean_inputs,
            }

            return AgentMessage(
                run_id=context.run.id,
                node_id=context.current_node_id or self.type_key.value,
                status=NodeRunStatus.COMPLETED,
                data=output_data,
                metadata=MessageMetadata(
                    prompt_tokens=loop_result.total_prompt_tokens,
                    completion_tokens=loop_result.total_completion_tokens,
                    total_tokens=loop_result.total_tokens,
                    cost_usd=loop_result.total_cost_usd,
                    model=config.model or "default",
                ),
            )

        # Fallback to direct completion if no tools assigned to this node
        llm_resp = await complete(
            messages=messages,
            model=config.model,
            temperature=0.0,
            max_tokens=4096,
        )

        return AgentMessage(
            run_id=context.run.id,
            node_id=context.current_node_id or self.type_key.value,
            status=NodeRunStatus.COMPLETED,
            data={
                "result": llm_resp.content,
                "content": llm_resp.content,
                "status": "completed",
                **clean_inputs,
            },
            metadata=MessageMetadata(
                prompt_tokens=llm_resp.prompt_tokens,
                completion_tokens=llm_resp.completion_tokens,
                total_tokens=llm_resp.total_tokens,
                cost_usd=llm_resp.cost_usd,
                model=llm_resp.model,
            ),
        )
