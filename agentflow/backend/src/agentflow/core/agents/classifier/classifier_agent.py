"""
Classifier / Router Agent — scores and categorizes input, picks a branch.

This agent serves two roles:
  1. As a scorer: assigns numeric scores to research output (e.g., lead quality 1-10)
  2. As a router: emits a "branch" field that edge conditions can evaluate

For the demo workflow, it reads ResearchOutput and produces a quality score
so the subsequent edge condition (score >= 7) can decide whether to continue.

Output schema:
  - score: int 1-10 (lead quality)
  - category: string label
  - branch: string ("qualified" | "not_qualified") for routing
  - reasoning: explanation of the score
  - recommendation: what to do next
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar

import structlog
from pydantic import BaseModel, Field

from agentflow.core.agents.base import BaseAgent
from agentflow.core.llm.structured import complete_structured
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


class ClassifierOutput(BaseModel):
    """Structured output from the Classifier/Router agent."""
    score: int = Field(ge=1, le=10, description="Quality score 1 (poor) to 10 (excellent)")
    category: str = Field(description="Category label, e.g. 'enterprise', 'smb', 'startup'")
    branch: str = Field(description="Routing branch: 'qualified' or 'not_qualified'")
    reasoning: str = Field(description="2-3 sentence explanation of the score")
    recommendation: str = Field(description="Suggested next action")
    # Pass-through fields for downstream agents
    lead_name: str | None = None
    company: str | None = None


class ClassifierAgent(BaseAgent):
    """
    Scores incoming data and emits a routing branch.

    Expected input: ResearchOutput fields (summary, key_findings, confidence)
    Output: ClassifierOutput with score and branch for conditional edges.

    The edge condition in the demo workflow reads: output.score >= 7
    """

    type_key: ClassVar[AgentType] = AgentType.ROUTER

    async def run(
        self,
        input_data: dict[str, Any],
        config: NodeConfig,
        context: RunContext,
        tools: list[BaseTool],
    ) -> AgentMessage:
        trigger = context.run.trigger_data or {}
        lead_name = input_data.get("lead_name") or trigger.get("lead_name", "")
        company = input_data.get("company") or trigger.get("company", "")
        goal = input_data.get("goal") or trigger.get("goal", "")
        summary = input_data.get("summary", "")
        key_findings = input_data.get("key_findings", [])
        confidence = input_data.get("confidence", 0.5)
        validation_feedback = input_data.get("_validation_feedback")

        # Fallback to snapshots or context outputs if research summary is missing
        if not summary:
            snap = input_data.get("data_snapshot")
            if isinstance(snap, dict) and snap.get("summary"):
                summary = snap.get("summary", "")
                key_findings = snap.get("key_findings", [])
                confidence = snap.get("confidence", confidence)
            else:
                for out in context.get_all_outputs().values():
                    if isinstance(out, dict) and out.get("summary"):
                        summary = out.get("summary", "")
                        if not key_findings and out.get("key_findings"):
                            key_findings = out.get("key_findings", [])
                        if out.get("confidence"):
                            confidence = out.get("confidence", confidence)
                        break

        # Check if outreach has already been approved by a human or upstream gate
        is_human_approved = (
            input_data.get("approved") is True
            or (isinstance(input_data.get("data_snapshot"), dict) and input_data["data_snapshot"].get("approved") is True)
        )

        system_prompt = config.system_prompt or (
            "You are a sales qualification specialist. "
            "You score leads and companies based on research data. "
            "Be honest and critical — not every lead deserves a high score. "
            "Use the ICP (ideal customer profile) framework. "
            "A score of 7+ means 'qualified for outreach'. "
            "If a lead or outreach draft has already been explicitly approved by a human operator, "
            "respect that approval and score the lead as qualified unless clear disqualifiers exist."
        )

        findings_text = "\n".join(
            f"- [{f.get('relevance_score', 0):.1f}] {f.get('title', '')}: {f.get('detail', '')}"
            for f in key_findings
        ) if key_findings else "No findings provided."

        approval_notice = (
            "\nNote: This lead and outreach email have been explicitly reviewed and APPROVED by a human operator.\n"
            if is_human_approved
            else ""
        )

        user_content = f"""Score this lead for B2B sales qualification:{approval_notice}

Lead: {lead_name or "Unknown"}
Company: {company or "Unknown"}
Goal: {goal or "Sales outreach"}
Research confidence: {confidence:.0%}

Research summary:
{summary}

Key findings:
{findings_text}

Score this lead 1-10 and determine if they are qualified for outreach.
A score >= 7 means qualified. Set branch to 'qualified' or 'not_qualified' accordingly.
"""

        messages: list[dict[str, str]] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ]

        result, llm_resp = await complete_structured(
            messages=messages,
            output_model=ClassifierOutput,
            model=config.model,
            validation_feedback=validation_feedback,
        )

        output_data = result.model_dump()
        if not output_data.get("lead_name") and lead_name:
            output_data["lead_name"] = lead_name
        if not output_data.get("company") and company:
            output_data["company"] = company

        # Preserve downstream content keys (subject, body, email, etc.)
        for k in (
            "subject", "body", "email_content", "to_email", "goal",
            "summary", "topic", "approved", "notes", "reviewer",
        ):
            if k in input_data and k not in output_data:
                output_data[k] = input_data[k]

        log.info(
            "classifier_completed",
            lead_name=lead_name,
            score=result.score,
            branch=result.branch,
        )

        return AgentMessage(
            run_id=context.run.id,
            node_id=context.current_node_id or "classifier",
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
