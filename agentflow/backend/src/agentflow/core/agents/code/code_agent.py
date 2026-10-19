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

log = structlog.get_logger(__name__)


class CodeAgent(BaseAgent):
    """Hybrid code execution primitive: deterministic Python sandbox + LLM transformation."""

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

        # ── 1. Deterministic Code Sandbox Execution ──────────────────────────
        if code_script or extra_cfg.get("execution_mode") == "deterministic":
            start_t = time.perf_counter()
            try:
                script_to_run = code_script or (
                    "# Default pass-through transformation\n"
                    "result = {'status': 'processed', **data}\n"
                )
                safe_globals = {
                    "__builtins__": {
                        "abs": abs, "min": min, "max": max, "len": len, "sum": sum,
                        "int": int, "float": float, "str": str, "bool": bool, "list": list,
                        "dict": dict, "set": set, "tuple": tuple, "enumerate": enumerate,
                        "zip": zip, "map": map, "filter": filter, "range": range, "round": round,
                        "isinstance": isinstance,
                    },
                    "json": json,
                    "data": dict(clean_inputs),
                    "inputs": dict(clean_inputs),
                    "result": None,
                    "output": None,
                }
                safe_locals: dict[str, Any] = {}
                exec(script_to_run, safe_globals, safe_locals)  # noqa: S102

                res = safe_locals.get("result") or safe_locals.get("output") or safe_globals.get("result") or safe_globals.get("output")
                if res is None:
                    transform_fn = safe_locals.get("transform") or safe_globals.get("transform")
                    if callable(transform_fn):
                        res = transform_fn(dict(clean_inputs))
                    else:
                        res = {k: v for k, v in safe_locals.items() if not k.startswith("_")} or clean_inputs

                output_dict = res if isinstance(res, dict) else {"result": res, "status": "completed"}
                for k, v in clean_inputs.items():
                    if k not in output_dict:
                        output_dict[k] = v
                duration_ms = int((time.perf_counter() - start_t) * 1000)

                log.info("deterministic_sandbox_executed", node_id=context.current_node_id, duration_ms=duration_ms)
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
                        model="sandbox/python3",
                    ),
                )
            except Exception as exc:
                log.warning("deterministic_execution_error_falling_back_to_llm", error=str(exc))
                # If script failed, fallback to LLM agent

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
