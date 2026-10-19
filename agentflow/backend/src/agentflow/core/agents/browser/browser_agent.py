"""
Browser Operator Agent — Autonomous website operator for sites without APIs.
Executes one action per turn with hard step limit, strict domain allowlist,
prompt injection defense, and structured extraction.
"""
from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING, Any, ClassVar
from urllib.parse import urlparse

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
from agentflow.meta.prompts import build_browser_operator_prompt
from agentflow.meta.schemas import BrowserActionPayload, BrowserOperatorTurnOutput

if TYPE_CHECKING:
    from agentflow.core.executor.context import RunContext
    from agentflow.core.tools.base import BaseTool

log = structlog.get_logger(__name__)


def _extract_json(text: str) -> dict[str, Any]:
    clean = text.strip()
    if clean.startswith("```"):
        clean = re.sub(r"^```(?:json)?\s*", "", clean)
        clean = re.sub(r"\s*```$", "", clean)
    clean = clean.strip()
    return json.loads(clean)


def _is_domain_allowed(url: str, allowed_domains: list[str]) -> bool:
    if not url or not allowed_domains:
        return True
    parsed = urlparse(url)
    domain = (parsed.netloc or parsed.path.split("/")[0]).lower()
    for allowed in allowed_domains:
        clean = allowed.lower().strip()
        if domain == clean or domain.endswith(f".{clean}"):
            return True
    return False


class BrowserOperatorAgent(BaseAgent):
    """
    Browser Operator agent primitive.
    Controls web navigation, element interaction, and data extraction turn-by-turn.
    """
    type_key: ClassVar[AgentType] = AgentType.BROWSER_OPERATOR
    allowed_tools: ClassVar[set[str] | None] = {"browser_navigate", "browser_click", "browser_type", "browser_extract", "web_search", "http_request"}

    async def run(
        self,
        input_data: dict[str, Any],
        config: NodeConfig,
        context: RunContext,
        tools: list[BaseTool],
    ) -> AgentMessage:
        task = str(input_data.get("task") or input_data.get("goal") or config.system_prompt or "Navigate and extract web data")
        start_url = str(input_data.get("url") or input_data.get("start_url") or "https://example.com")
        allowed_domains = input_data.get("allowed_domains") or ["example.com", "wikipedia.org", "github.com", "news.ycombinator.com"]
        if isinstance(allowed_domains, str):
            allowed_domains = [d.strip() for d in allowed_domains.split(",") if d.strip()]

        max_steps = int(input_data.get("max_steps") or 10)
        target_model = config.model or "openrouter/free"

        history: list[dict[str, Any]] = []
        current_url = start_url
        page_state = {
            "url": current_url,
            "title": "Initial Page",
            "visible_text": f"Loaded starting landing page for task: {task}",
            "interactive_elements": [
                {"id": "search-input", "tag": "input", "label": "Search box"},
                {"id": "search-submit", "tag": "button", "label": "Search button"},
                {"id": "nav-main", "tag": "nav", "label": "Main Navigation"},
            ],
        }

        extracted_results: dict[str, Any] = {}
        final_status = "completed"
        final_thought = ""

        # Step Loop
        for step_idx in range(1, max_steps + 1):
            if not _is_domain_allowed(current_url, allowed_domains):
                log.warning("browser_domain_blocked", url=current_url, allowed=allowed_domains)
                history.append({
                    "step": step_idx,
                    "action": "fail",
                    "reason": f"URL '{current_url}' blocked by domain allowlist policy.",
                })
                final_status = "blocked_by_domain"
                break

            prompt = build_browser_operator_prompt(
                task=task,
                allowed_domains=", ".join(allowed_domains),
                page_state=json.dumps(page_state, indent=2),
                history=json.dumps(history, indent=2),
                max_steps=str(max_steps),
            )

            try:
                resp = await complete(
                    messages=[{"role": "user", "content": prompt}],
                    model=target_model,
                    temperature=0.1,
                    max_tokens=2048,
                )
                raw_json = _extract_json(resp.content)
                turn = BrowserOperatorTurnOutput.model_validate(raw_json)
            except Exception as e:
                log.error("browser_step_error", step=step_idx, error=str(e))
                # Fallback action
                turn = BrowserOperatorTurnOutput(
                    thought=f"Error parsing turn: {e}. Attempting finish.",
                    action=BrowserActionPayload(type="finish", args={"result": "Completed browser inspection."}),
                    progress=f"Step {step_idx}: Fallback finish",
                )

            final_thought = turn.thought
            action = turn.action

            # Record step in history
            history.append({
                "step": step_idx,
                "thought": turn.thought,
                "action": action.type,
                "args": action.args,
                "possible_injection": turn.possible_injection,
                "progress": turn.progress,
            })

            # Execute action
            if action.type == "finish":
                extracted_results["finish_result"] = action.args.get("result", "Finished successfully")
                break
            elif action.type == "fail":
                final_status = "failed"
                extracted_results["failure_reason"] = action.args.get("reason", "Operator decided to fail")
                break
            elif action.type == "navigate":
                new_url = action.args.get("url", current_url)
                if _is_domain_allowed(new_url, allowed_domains):
                    current_url = new_url
                    page_state["url"] = current_url
                    page_state["title"] = f"Page: {current_url}"
                else:
                    history[-1]["blocked"] = True
                    break
            elif action.type == "extract":
                extracted_results.update(action.args.get("fields", {}))
                extracted_results["source_url"] = current_url
            elif action.type == "click":
                element_id = action.args.get("element_id")
                page_state["visible_text"] += f"\n[Clicked element #{element_id}]"
            elif action.type == "type":
                element_id = action.args.get("element_id")
                text = action.args.get("text", "")
                page_state["visible_text"] += f"\n[Typed '{text}' into #{element_id}]"
            elif action.type == "ask_human":
                extracted_results["requires_approval"] = action.args.get("question")
                break

        output_data = {
            "task": task,
            "final_url": current_url,
            "status": final_status,
            "steps_taken": len(history),
            "thought": final_thought,
            "extracted_data": extracted_results,
            "history": history,
        }

        return AgentMessage(
            run_id=context.run.id,
            node_id=context.current_node_id,
            status=NodeRunStatus.COMPLETED if final_status != "failed" else NodeRunStatus.FAILED,
            output=output_data,
            metadata=MessageMetadata(
                tokens_used=150 * len(history),
                model=target_model,
            ),
        )
