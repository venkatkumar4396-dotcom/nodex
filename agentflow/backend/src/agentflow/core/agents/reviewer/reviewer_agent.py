"""
Reviewer / Critic Agent — evaluates another agent's output against criteria.

This agent scores the Writer's output and can send it back for revision.
In the demo workflow, if score < 8, the executor re-routes to Writer with
the reviewer's feedback. The edge config includes max_iterations=2 to
prevent infinite loops.

Output schema:
  - score: 1-10 quality rating
  - passed: bool (score >= threshold)
  - feedback: specific actionable critique
  - strengths: what's good
  - improvements: what needs fixing
  - revised_subject (optional): if the reviewer wants to suggest one
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


class ReviewerOutput(BaseModel):
    """Structured output from the Reviewer/Critic agent."""
    score: int = Field(ge=1, le=10, description="Quality score 1-10")
    passed: bool = Field(description="True if quality meets threshold (score >= 8)")
    feedback: str = Field(description="Specific, actionable critique of the content")
    strengths: list[str] = Field(
        default_factory=list,
        description="What the content does well"
    )
    improvements: list[str] = Field(
        default_factory=list,
        description="Specific things to improve"
    )
    revised_subject: str | None = Field(
        default=None,
        description="Optional: suggested better subject line"
    )


class ReviewerAgent(BaseAgent):
    """
    Reviewer/Critic agent: evaluates content quality and requests revisions.

    Expected input:
      - subject: email subject line
      - body: email body
      - lead_name: recipient's name
      - company: recipient's company

    Config options (in NodeConfig.extra):
      - threshold: minimum score to pass (default: 8)
      - criteria: list of criteria strings to evaluate against
    """

    type_key: ClassVar[AgentType] = AgentType.REVIEWER

    async def run(
        self,
        input_data: dict[str, Any],
        config: NodeConfig,
        context: RunContext,
        tools: list[BaseTool],
    ) -> AgentMessage:
        subject = input_data.get("subject", "")
        body = input_data.get("body", "")
        lead_name = input_data.get("lead_name", "Unknown")
        company = input_data.get("company", "Unknown")
        tone = input_data.get("tone", "professional")
        personalization_hooks = input_data.get("personalization_hooks", [])
        validation_feedback = input_data.get("_validation_feedback")

        # Config-driven evaluation parameters
        threshold = config.extra.get("threshold", 8)
        criteria = config.extra.get("criteria", [
            "Personalization (references specific facts about the lead)",
            "Clarity (easy to understand, no jargon)",
            "Value proposition (clear benefit to recipient)",
            "Call to action (specific, low-friction ask)",
            "Length (concise, under 150 words)",
            "Tone (matches intended tone: professional)",
            "No generic phrases (no 'I hope this finds you well')",
        ])

        system_prompt = config.system_prompt or (
            "You are a senior marketing editor and B2B email specialist. "
            "You evaluate outreach emails with high standards. "
            "Be honest and specific — vague praise helps no one. "
            f"An email passes only if it scores {threshold} or above. "
            "Score it against the given criteria ruthlessly."
        )

        criteria_text = "\n".join(f"{i+1}. {c}" for i, c in enumerate(criteria))
        hooks_text = ", ".join(personalization_hooks) if personalization_hooks else "none detected"

        user_content = f"""Review this outreach email:

RECIPIENT: {lead_name} at {company}
INTENDED TONE: {tone}
PERSONALIZATION HOOKS USED: {hooks_text}

SUBJECT: {subject}

BODY:
{body}

---
Evaluate against these criteria:
{criteria_text}

Score 1-10 and set passed=true only if score >= {threshold}.
Provide specific, actionable feedback referencing actual lines from the email.
"""

        messages: list[dict[str, str]] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ]

        result, llm_resp = await complete_structured(
            messages=messages,
            output_model=ReviewerOutput,
            model=config.model,
            validation_feedback=validation_feedback,
        )

        output_data = result.model_dump()
        # Pass through the original content for downstream nodes
        output_data.update({
            "subject": subject,
            "body": body,
            "lead_name": lead_name,
            "company": company,
            # Merge reviewer feedback into writer's next input
            "review_feedback": result.feedback,
            "review_improvements": result.improvements,
        })

        log.info(
            "reviewer_completed",
            lead_name=lead_name,
            score=result.score,
            passed=result.passed,
            improvements_count=len(result.improvements),
        )

        return AgentMessage(
            run_id=context.run.id,
            node_id=context.current_node_id or "reviewer",
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
