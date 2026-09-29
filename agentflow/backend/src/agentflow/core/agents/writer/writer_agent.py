"""
Writer Agent — composes tailored outreach emails or other written content.

Input: research summary + classifier output (score, category, lead context)
Output: structured email with subject, body, tone, word count

Design: The Writer's system prompt is configurable per-node (tone, style,
purpose). The demo uses it for cold outreach emails, but the same agent
can write blog posts, Slack messages, or support replies.

Prompt injection defense: research findings are wrapped as cited data,
not as direct instructions to the model.
"""
from __future__ import annotations

from typing import Any, ClassVar, TYPE_CHECKING
from pydantic import BaseModel, Field

import structlog

from agentflow.core.agents.base import BaseAgent
from agentflow.core.llm.structured import complete_structured, StructuredOutputError
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


class WriterOutput(BaseModel):
    """Structured output from the Writer agent."""
    subject: str = Field(description="Email subject line (under 60 chars)")
    body: str = Field(description="Full email body in plain text")
    tone: str = Field(description="Tone used: professional, friendly, direct, etc.")
    word_count: int = Field(ge=10, description="Approximate word count of the body")
    personalization_hooks: list[str] = Field(
        default_factory=list,
        description="List of specific facts used to personalize the email"
    )


class WriterAgent(BaseAgent):
    """
    Writer agent: composes personalized outreach content.

    Expected input (from edge data_map):
      - summary: research summary
      - lead_name: person's name
      - company: company name
      - score: qualification score (from classifier)
      - category: lead category

    Config options (in NodeConfig.extra):
      - tone: "professional" | "friendly" | "direct" (default: "professional")
      - max_words: target max word count (default: 150)
      - purpose: what the email is for (default: "sales outreach")
    """

    type_key: ClassVar[AgentType] = AgentType.WRITER

    async def run(
        self,
        input_data: dict[str, Any],
        config: NodeConfig,
        context: "RunContext",
        tools: list["BaseTool"],
    ) -> AgentMessage:
        summary = input_data.get("summary", "")
        key_findings = input_data.get("key_findings", [])
        lead_name = input_data.get("lead_name", "Unknown")
        company = input_data.get("company", "Unknown Company")
        score = input_data.get("score", 0)
        category = input_data.get("category", "unknown")
        recommendation = input_data.get("recommendation", "")
        validation_feedback = input_data.get("_validation_feedback")

        # Config-driven writing parameters
        tone = config.extra.get("tone", "professional")
        max_words = config.extra.get("max_words", 150)
        purpose = config.extra.get("purpose", "sales outreach")
        sender_name = config.extra.get("sender_name", "Alex")
        sender_company = config.extra.get("sender_company", "AgentFlow")

        system_prompt = config.system_prompt or (
            f"You are an expert B2B copywriter specializing in {purpose}. "
            f"Write in a {tone} tone. Be concise, specific, and human. "
            f"Never use generic openers like 'I hope this finds you well'. "
            f"Reference specific facts from the research to show you've done your homework. "
            f"Target length: {max_words} words maximum."
        )

        # Wrap research data as cited information (prompt injection defense)
        findings_text = "\n".join(
            f"- {f.get('title', '')}: {f.get('detail', '')}"
            for f in key_findings[:5]  # limit to top 5
        ) if key_findings else "General research data available."

        user_content = f"""Write a personalized {purpose} email.

RECIPIENT CONTEXT (use these facts for personalization):
- Name: {lead_name}
- Company: {company}
- Lead category: {category}
- Qualification score: {score}/10
- Research summary: {summary}
- Key facts to reference:
{findings_text}
- Recommended angle: {recommendation}

SENDER: {sender_name} from {sender_company}

Write a compelling, personalized email that:
1. Opens with something specific about them (not generic)
2. Connects their situation to your solution
3. Has a clear, low-friction call to action
4. Stays under {max_words} words
"""

        messages: list[dict[str, str]] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ]

        try:
            result, llm_resp = await complete_structured(
                messages=messages,
                output_model=WriterOutput,
                model=config.model,
                validation_feedback=validation_feedback,
            )
        except StructuredOutputError:
            raise

        output_data = result.model_dump()
        output_data.update({"lead_name": lead_name, "company": company})

        log.info(
            "writer_completed",
            lead_name=lead_name,
            subject=result.subject,
            word_count=result.word_count,
        )

        return AgentMessage(
            run_id=context.run.id,
            node_id=context.current_node_id or "writer",
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
