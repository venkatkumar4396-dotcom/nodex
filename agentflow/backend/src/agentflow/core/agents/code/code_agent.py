"""
Code Agent — Code sandbox and computation primitive.

Handles custom data transformations, mathematical aggregation, schema reshaping,
and structured scripting over upstream node outputs.
"""
from __future__ import annotations

import json
import time
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

from agentflow.core.sandbox import (
    SandboxExecutionError,
    SandboxSecurityError,
    SandboxTimeoutError,
    run_in_sandbox,
)

log = structlog.get_logger(__name__)


class CodeAgent(BaseAgent):
    """Hybrid code execution primitive: isolated deterministic sandbox + LLM transformation."""

    type_key: ClassVar[AgentType] = AgentType.CODE
    allowed_tools: ClassVar[set[str] | None] = {"python_eval", "code_exec", "sandbox_exec", "file", "web_search", "http_request"}

    async def run(
        self,
        input_data: dict[str, Any],
        config: NodeConfig,
        context: RunContext,
        tools: list[BaseTool],
    ) -> AgentMessage:
        clean_inputs = {k: v for k, v in input_data.items() if not k.startswith("_")}
        extra_cfg = config.extra or {}
        code_script = extra_cfg.get("code") or extra_cfg.get("script") or extra_cfg.get("python_code")

        # ── 1. Isolated Code Sandbox Execution (Subprocess / Container) ───────
        if code_script or extra_cfg.get("execution_mode") == "deterministic":
            start_t = time.perf_counter()
            script_to_run = code_script or (
                "# Default pass-through transformation\n"
                "result = {'status': 'processed', **data}\n"
            )
            timeout = float(config.timeout_seconds or 10.0)

            try:
                res_data = await run_in_sandbox(
                    code=script_to_run,
                    input_data=clean_inputs,
                    timeout_seconds=timeout,
                )
                output_dict = res_data if isinstance(res_data, dict) else {"result": res_data, "status": "completed"}
                for k, v in clean_inputs.items():
                    if k not in output_dict:
                        output_dict[k] = v
                duration_ms = int((time.perf_counter() - start_t) * 1000)

                log.info("isolated_sandbox_executed", node_id=context.current_node_id, duration_ms=duration_ms)
                return AgentMessage(
                    run_id=context.run.id,
                    node_id=context.current_node_id or self.type_key.value,
                    status=NodeRunStatus.COMPLETED,
                    data=output_dict,
                    metadata=MessageMetadata(
                        prompt_tokens=0,
                        completion_tokens=0,
                        total_tokens=0,
                        cost_usd=0.0,
                        latency_ms=duration_ms,
                        model="sandbox/isolated",
                    ),
                )
            except SandboxSecurityError as sec_err:
                duration_ms = int((time.perf_counter() - start_t) * 1000)
                log.error("sandbox_security_violation_blocked", node_id=context.current_node_id, error=str(sec_err))
                return AgentMessage(
                    run_id=context.run.id,
                    node_id=context.current_node_id or self.type_key.value,
                    status=NodeRunStatus.FAILED,
                    errors=[f"Security violation blocked: {sec_err}"],
                    data={"error": str(sec_err), "status": "blocked"},
                    metadata=MessageMetadata(
                        prompt_tokens=0,
                        completion_tokens=0,
                        total_tokens=0,
                        cost_usd=0.0,
                        latency_ms=duration_ms,
                        model="sandbox/blocked",
                    ),
                )
            except (SandboxExecutionError, SandboxTimeoutError) as exc:
                duration_ms = int((time.perf_counter() - start_t) * 1000)
                log.error("sandbox_execution_failed", node_id=context.current_node_id, error=str(exc))
                return AgentMessage(
                    run_id=context.run.id,
                    node_id=context.current_node_id or self.type_key.value,
                    status=NodeRunStatus.FAILED,
                    errors=[f"Sandbox execution failed: {exc}"],
                    data={"error": str(exc), "status": "failed"},
                    metadata=MessageMetadata(
                        prompt_tokens=0,
                        completion_tokens=0,
                        total_tokens=0,
                        cost_usd=0.0,
                        latency_ms=duration_ms,
                        model="sandbox/failed",
                    ),
                )

        # ── 2. LLM Transformation Primitive (with self-healing fallback) ─────
        system_prompt = config.system_prompt or (
            "You are a specialized Code & Data Transformation Agent. "
            "Inspect the input data, perform any required mathematical, structural, or logical transformations, "
            "and output the final transformed result with clean explanations."
        )

        payload_str = json.dumps(clean_inputs, indent=2, ensure_ascii=False) if clean_inputs else "{}"

        messages = [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": f"Transform and compute the following input payload:\n\n```json\n{payload_str}\n```",
            },
        ]

        llm_resp = await complete(
            messages=messages,
            model=config.model,
            temperature=0.0,
            max_tokens=4096,
            fallback_models=getattr(config, "fallback_models", None),
        )

        output_data = {
            "result": llm_resp.content,
            "transformed_content": llm_resp.content,
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
