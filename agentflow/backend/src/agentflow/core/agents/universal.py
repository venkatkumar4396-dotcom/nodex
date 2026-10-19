"""
Universal Agent — dynamic fallback agent for any unspecialized AgentType.
Allows every node type in the UI palette to execute gracefully.
"""
from __future__ import annotations

import json
import re
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


def _parse_clean_output(raw_text: str) -> dict[str, Any]:
    """Parse raw LLM output into clean structured dictionary fields, stripping leaked thoughts."""
    text = (raw_text or "").strip()
    if not text:
        return {"result": "", "summary": "No output produced"}

    # Strip any reasoning tags and thought processes
    text = re.sub(
        r"<(?:think|thought|reasoning)[^>]*>[\s\S]*?</(?:think|thought|reasoning)>",
        "",
        text,
        flags=re.IGNORECASE,
    ).strip()
    text = re.sub(
        r"^(?:Here'?s a thinking process:?|Thinking Process:?|Thought Process:?)[\s\S]*?(?=\n\n(?:[A-Z0-9#*`{\[]|\b(?:Here is|Subject|Title|Notification|Hi|Hello|Dear|Alert|Status|Summary)))",
        "",
        text,
        flags=re.IGNORECASE,
    ).strip()
    if not text and raw_text:
        text = raw_text.strip()

    # Attempt direct JSON
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            if "result" not in data:
                data["result"] = text
            return data
    except (json.JSONDecodeError, TypeError, ValueError):
        pass

    # Attempt markdown codeblock JSON: ```json ... ```
    match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
    if match:
        try:
            data = json.loads(match.group(1).strip())
            if isinstance(data, dict):
                if "result" not in data:
                    data["result"] = text
                return data
        except (json.JSONDecodeError, TypeError, ValueError):
            pass

    # Clean text fallback: provide clean summary
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    first_line = lines[0] if lines else "Execution completed."
    if len(first_line) > 250:
        first_line = first_line[:250] + "..."

    return {
        "result": text,
        "summary": first_line,
    }


class UniversalAgent(BaseAgent):
    """Fallback agent capable of handling any AgentType dynamically."""

    type_key: ClassVar[AgentType] = AgentType.SUMMARIZER

    def __init__(self, agent_type: AgentType | None = None) -> None:
        self._agent_type = agent_type or AgentType.SUMMARIZER

    async def run(
        self,
        input_data: dict[str, Any],
        config: NodeConfig,
        context: RunContext,
        tools: list[BaseTool],
    ) -> AgentMessage:
        DEFAULT_PROMPTS = {
            AgentType.TRIGGER_WEBHOOK: (
                "You are a Webhook Ingestion Agent. Parse incoming HTTP webhook payloads, "
                "validate headers and body schema, extract key payload entities, and format data for downstream processing."
            ),
            AgentType.TRIGGER_CRON: (
                "You are a Scheduled Cron Trigger Agent. Initiate periodic workflow execution, "
                "supply execution timestamps, and construct initial execution state parameters."
            ),
            AgentType.SCRAPER: (
                "You are an intelligent Web Scraper and Content Reader Agent. Parse given URLs, "
                "extract clean article text and tabular data, remove advertisement clutter, and structure output clearly."
            ),
            AgentType.SQL: (
                "You are an expert Database and SQL Agent. Formulate secure, performant SQL queries, "
                "inspect database schema definitions, and interpret relational result sets into concise summaries."
            ),
            AgentType.DOCUMENT_PARSER: (
                "You are an intelligent Document and PDF Parser Agent. Extract structured text, "
                "tables, key-value pairs, and financial line items from documents, contracts, and forms."
            ),
            AgentType.VISION: (
                "You are a Multimodal Vision Agent. Analyze images, screenshots, UI mockups, "
                "diagrams, and chart visuals with deep visual comprehension and structured findings."
            ),
            AgentType.SUMMARIZER: (
                "You are an Executive Summarizer Agent. Condense long articles, transcripts, "
                "and research dumps into high-signal executive takeaways, key metrics, and action points."
            ),
            AgentType.TRANSLATOR: (
                "You are a Professional Translation and Localization Agent. Translate content accurately "
                "while preserving tone, intent, nuance, and domain-specific terminology across languages."
            ),
            AgentType.DATA_ANALYST: (
                "You are an expert Data Analyst Agent. Analyze structured data, calculate statistical "
                "metrics, identify trends and anomalies, and prepare clean structured payloads for charts."
            ),
            AgentType.VALIDATOR: (
                "You are a Schema and Data Quality Validation Agent. Verify input against schema requirements, "
                "detect missing fields, type mismatches, or malformed data, and output a structured validation report."
            ),
            AgentType.GUARDRAIL: (
                "You are an AI Guardrail and Safety Agent. Audit inputs and outputs for PII data, "
                "prompt injections, toxic content, and hallucinations. Redact sensitive values and enforce safety policies."
            ),
            AgentType.HTTP_API: (
                "You are an HTTP API Integration Agent. Formulate and execute REST API requests, "
                "handle JSON headers and payloads, and format HTTP responses for downstream processing."
            ),
            AgentType.SPREADSHEET: (
                "You are a Spreadsheet and Tabular Data Agent. Process CSV and Excel rows, "
                "perform filtering and aggregations, and output cleanly formatted tabular results."
            ),
            AgentType.MESSAGING: (
                "You are a Messaging and Channel Notification Agent. Format and dispatch clear, "
                "engaging alerts, status updates, and interactive rich message cards for Slack and Teams. "
                "Return ONLY the finalized card text or notification message. Do not output any thought process, analysis, reasoning steps, or conversational preamble."
            ),
            AgentType.GITHUB_OPS: (
                "You are a GitHub Ops Automation Agent. Triage issues, review pull request diffs, "
                "summarize code changes, and manage repository workflow automation."
            ),
            AgentType.ERROR_HANDLER: (
                "You are an Error Boundary and Recovery Agent. Intercept upstream failure data, "
                "diagnose root cause, formulate error summaries, and execute safe fallback branches."
            ),
        }

        agent_label = self._agent_type.value.replace("_", " ").title()
        system_prompt = config.system_prompt or DEFAULT_PROMPTS.get(
            self._agent_type,
            f"You are an AI {agent_label} Agent in an automated workflow. "
            f"Process the given input data and deliver high quality, clear results."
        )

        target_url = input_data.get("target_url") or input_data.get("url") or ""
        user_task = input_data.get("user_task") or input_data.get("task") or input_data.get("query") or ""

        url_text = f"\nTarget URL / Website: {target_url}" if target_url else ""
        task_text = f"\nSpecific Instructions: {user_task}" if user_task else ""

        messages = [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": (
                    f"Execute your task on the following input data:{url_text}{task_text}\n\n"
                    f"Input Payload:\n{input_data}\n\n"
                    f"Analyze all inputs, execute any required tool calls or data processing, "
                    f"and deliver high quality, structured results."
                ),
            },
        ]

        if tools:
            from agentflow.core.tools.tool_loop import run_tool_loop
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
                log.info("universal_agent_awaiting_approval", node_id=context.current_node_id)
                return AgentMessage(
                    run_id=context.run.id,
                    node_id=context.current_node_id or self._agent_type.value,
                    status=NodeRunStatus.AWAITING_APPROVAL,
                    data={
                        "summary": "Execution paused awaiting human approval for destructive action.",
                        "pending_approval": context.get_shared(f"pending_approval_{context.current_node_id}"),
                        "tool_trace": [s.model_dump() for s in loop_result.trace],
                        "agent_type": self._agent_type.value,
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
                final_content = f"Completed {len(loop_result.tool_results)} tool execution(s)."

            parsed_data = _parse_clean_output(final_content)
            output_data = {
                **parsed_data,
                "status": "completed",
                "agent_type": self._agent_type.value,
                "tool_calls_count": len(loop_result.tool_results),
                "tool_trace": [s.model_dump() for s in loop_result.trace],
            }
            return AgentMessage(
                run_id=context.run.id,
                node_id=context.current_node_id or self._agent_type.value,
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

        llm_resp = await complete(
            messages=messages,
            model=config.model,
            temperature=0.0,
            max_tokens=2048,
        )

        parsed_data = _parse_clean_output(llm_resp.content)
        output_data = {
            **parsed_data,
            "status": "completed",
            "agent_type": self._agent_type.value,
        }

        return AgentMessage(
            run_id=context.run.id,
            node_id=context.current_node_id or self._agent_type.value,
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
